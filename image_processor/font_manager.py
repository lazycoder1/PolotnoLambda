"""
Font management module for the image processor.
Handles font fetching from Google Fonts API, S3 storage, and Lambda /tmp caching.
"""

import os
import logging
from typing import Optional
from PIL import ImageFont
import requests
import boto3
from botocore.exceptions import ClientError

# Setup logger for this module
logger = logging.getLogger(__name__)

# Constants
TMP_DIR = "/tmp"
DEFAULT_FONT_S3_PREFIX = "fonts/"
DEFAULT_FONT_PATH = "fonts/Roboto-Regular.ttf"  # Default relative to project root

# Variant mapping from common names to Google Fonts API names
VARIANT_MAPPING = {
    "Regular": "regular",
    "Italic": "italic",
    "Bold": "700",
    "Bold Italic": "700italic",
    "Light": "300",
    "Light Italic": "300italic",
    "Medium": "500",
    "Medium Italic": "500italic",
    "SemiBold": "600",
    "SemiBold Italic": "600italic",
    "ExtraBold": "800",
    "ExtraBold Italic": "800italic",
    "Black": "900",
    "Black Italic": "900italic",
    # Add numeric weights directly
    **{str(w): str(w) for w in range(100, 1000, 100)},
    **{str(w) + "italic": str(w) + "italic" for w in range(100, 1000, 100)},
}

class FontManager:
    """
    Manages font fetching from Google Fonts API, S3 storage, and Lambda /tmp caching.
    """

    def __init__(self, s3_bucket_name: str, google_api_key: str, default_font_path: str = None):
        """
        Initialize FontManager with S3 bucket name and Google API key.

        Args:
            s3_bucket_name: Name of the S3 bucket where fonts are stored
            google_api_key: Google Fonts API key for fetching fonts
            default_font_path: Path to the default font to use when all other strategies fail
        """
        self.s3_bucket_name = s3_bucket_name
        self.google_api_key = google_api_key
        self.s3_client = boto3.client("s3")

        # Set default font path (use provided path or compute from current directory)
        if default_font_path:
            self.default_font_path = default_font_path
        else:
            self.default_font_path = os.path.join(os.getcwd(), DEFAULT_FONT_PATH)
            
        # Check if default font exists 
        if not os.path.exists(self.default_font_path):
            logger.warning(
                f"Default font not found at {self.default_font_path}. "
                f"Fallback to this font may fail if Google Fonts API and S3 strategies fail."
            )

        if not os.path.exists(TMP_DIR):
            os.makedirs(TMP_DIR, exist_ok=True)
        
        if not self.google_api_key:
            logger.warning(
                "FontManager initialized without a GOOGLE_API_KEY. "
                "Fetching new fonts from Google Fonts will fail. "
                "Font retrieval will rely on S3 and default font fallback."
            )

    def get_font(self, family_name: str, variant_name: str = "Regular", font_size: int = 12) -> Optional[ImageFont.FreeTypeFont]:
        """
        Get a font from cache, S3, Google Fonts API, or default font.

        Args:
            family_name: Font family name (e.g., "Roboto")
            variant_name: Font variant (e.g., "Regular", "Bold")
            font_size: Font size in points

        Returns:
            PIL ImageFont object or None if font cannot be loaded
        """
        # Get font file path
        font_path = self.get_font_path(family_name, variant_name)
        if not font_path:
            logger.error(f"Could not get font path for {family_name} {variant_name}. Will try default font.")
            if os.path.exists(self.default_font_path):
                logger.info(f"Using default font at {self.default_font_path}")
                font_path = self.default_font_path
            else:
                logger.error(f"Default font at {self.default_font_path} is not accessible.")
                return None

        # Load font with PIL
        try:
            font = ImageFont.truetype(font_path, font_size)
            logger.info(f"Successfully loaded font: {font_path} size: {font_size}")
            return font
        except Exception as e:
            logger.error(f"Failed to load font {font_path} with size {font_size}: {e}")
            
            # If loading the requested or default font failed, try PIL's default font
            try:
                logger.warning("Attempting to use Pillow's built-in default font.")
                return ImageFont.load_default()
            except Exception as e_default:
                logger.error(f"Failed to load even Pillow's default font: {e_default}")
                return None

    def get_font_path(self, family_name: str, variant_name: str = "Regular") -> Optional[str]:
        """
        Get the path to a font file, fetching it if necessary.

        Args:
            family_name: Font family name
            variant_name: Font variant name

        Returns:
            Path to the font file or None if font cannot be retrieved
        """
        api_variant_name = self._get_api_variant_name(variant_name)
        font_filename = self._generate_font_filename(family_name, api_variant_name)
        local_font_path = os.path.join(TMP_DIR, font_filename)
        s3_key = self._get_s3_key(font_filename)

        # 1. Check /tmp cache first
        if os.path.exists(local_font_path):
            logger.info(f"Font found in /tmp cache: {local_font_path}")
            return local_font_path

        # 2. Try S3
        if self._check_s3_exists(s3_key):
            if self._download_from_s3(s3_key, local_font_path):
                return local_font_path
            logger.warning(f"Failed to download {s3_key} from S3. Attempting Google Fonts.")
        
        # 3. Try Google Fonts API
        font_family_data = self._fetch_from_google_fonts_api(family_name)
        if font_family_data:
            files = font_family_data.get("files", {})
            font_url = files.get(api_variant_name)
            
            # Try fallback for common weight variations
            if not font_url and api_variant_name == "700":  # bold
                font_url = files.get("regular")
                if font_url: logger.info(f"Variant '700' (Bold) not found for {family_name}, trying 'regular'.")
            elif not font_url and api_variant_name == "700italic":
                font_url = files.get("italic")
                if font_url: logger.info(f"Variant '700italic' (Bold Italic) not found for {family_name}, trying 'italic'.")

            if font_url:
                if self._download_font_url(font_url, local_font_path):
                    self._upload_to_s3(local_font_path, s3_key)
                    return local_font_path
            else:
                logger.warning(f"Variant '{api_variant_name}' not found for family '{family_name}'. Available: {list(files.keys())}")
        else:
            logger.warning(f"Font family '{family_name}' not found or error fetching from Google Fonts.")

        # All methods failed - return None, and let get_font handle fallback to default
        return None

    def _get_api_variant_name(self, client_variant_name: str) -> str:
        """Convert client-friendly variant name to Google Fonts API variant name."""
        if isinstance(client_variant_name, str) and client_variant_name.lower() in (v.lower() for v in VARIANT_MAPPING.keys() if not v.isdigit()):
            normalized_client_variant = client_variant_name.capitalize()
        else:
            normalized_client_variant = client_variant_name
        return VARIANT_MAPPING.get(normalized_client_variant, str(client_variant_name).lower())

    def _generate_font_filename(self, family_name: str, api_variant_name: str) -> str:
        """Generate a standardized font filename."""
        safe_family_name = family_name.replace(" ", "")
        return f"{safe_family_name}-{api_variant_name}.ttf"

    def _get_s3_key(self, font_filename: str) -> str:
        """Generate the S3 key for the font file."""
        return f"{DEFAULT_FONT_S3_PREFIX}{font_filename}"

    def _check_s3_exists(self, s3_key: str) -> bool:
        """Check if a font file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.s3_bucket_name, Key=s3_key)
            logger.info(f"Font found in S3: s3://{self.s3_bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.info(f"Font not found in S3: s3://{self.s3_bucket_name}/{s3_key}")
                return False
            else:
                logger.error(f"Error checking S3 for {s3_key}: {e}")
                return False

    def _download_from_s3(self, s3_key: str, local_path: str) -> bool:
        """Download a file from S3 to the local path."""
        try:
            self.s3_client.download_file(self.s3_bucket_name, s3_key, local_path)
            logger.info(f"Successfully downloaded {s3_key} from S3 to {local_path}")
            return True
        except ClientError as e:
            logger.error(f"Error downloading {s3_key} from S3: {e}")
            return False

    def _fetch_from_google_fonts_api(self, family_name: str) -> Optional[dict]:
        """Query the Google Fonts API for a font family."""
        if not self.google_api_key:
            logger.warning("Cannot fetch from Google Fonts API: API key is missing.")
            return None
            
        api_url = f"https://www.googleapis.com/webfonts/v1/webfonts?key={self.google_api_key}&family={family_name.replace(' ', '+')}"
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("items"):
                return data["items"][0]
            else:
                logger.warning(f"Font family '{family_name}' not found in Google Fonts API response.")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching font '{family_name}' from Google Fonts API: {e}")
            return None
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Error parsing Google Fonts API response for '{family_name}': {e}")
            return None

    def _download_font_url(self, font_url: str, local_path: str) -> bool:
        """Download a font from a direct URL to a local path."""
        try:
            response = requests.get(font_url, stream=True, timeout=20)
            response.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"Successfully downloaded font from {font_url} to {local_path}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading font from URL {font_url}: {e}")
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except OSError:
                    pass
            return False

    def _upload_to_s3(self, local_path: str, s3_key: str) -> bool:
        """Upload a file from the local path to S3."""
        try:
            self.s3_client.upload_file(local_path, self.s3_bucket_name, s3_key)
            logger.info(f"Successfully uploaded {local_path} to s3://{self.s3_bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Error uploading {local_path} to S3 ({s3_key}): {e}")
            return False
        except FileNotFoundError:
            logger.error(f"File not found for S3 upload: {local_path}")
            return False 