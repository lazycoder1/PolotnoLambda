"""
Image handler module.
Handles loading, processing, and transforming images.
"""

from PIL import Image
import requests
from io import BytesIO
from typing import Dict, Any, Tuple, Optional

from .image_effects import apply_image_effects, create_rounded_corners, rotate_image
from .config import CONFIG
from .logger import get_logger

logger = get_logger(__name__)

def load_image_from_url(url: str) -> Image.Image:
    """Load image from URL and return PIL Image object"""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for bad responses
        img = Image.open(BytesIO(response.content))
        # Ensure the image has an alpha channel if it's not already in RGBA mode
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        return img
    except requests.RequestException as e:
        logger.error(f"Failed to load image from URL '{url}': {e}")
        raise
    except Exception as e:
        logger.error(f"Error processing image from URL '{url}': {e}")
        raise

def process_image(image_data: Dict[str, Any]) -> Tuple[Image.Image, Tuple[int, int]]:
    """Process a single image with all its properties"""
    try:
        # Validate input
        if not isinstance(image_data, dict) or 'src' not in image_data:
            raise ValueError("Invalid image data: missing 'src' field")
            
        # Load the image
        img = load_image_from_url(image_data['src'])
        
        # Get original dimensions for proper scaling
        orig_width, orig_height = img.size
        
        # Calculate target dimensions
        target_width = int(image_data['width'])
        target_height = int(image_data['height'])
        
        # Apply cropping if specified - relative to original image size
        if all(key in image_data for key in ['cropX', 'cropY', 'cropWidth', 'cropHeight']):
            crop_x = int(image_data['cropX'] * orig_width)
            crop_y = int(image_data['cropY'] * orig_height)
            crop_right = int((image_data['cropX'] + image_data['cropWidth']) * orig_width)
            crop_bottom = int((image_data['cropY'] + image_data['cropHeight']) * orig_height)
            # Ensure crop coordinates are valid
            crop_x = max(0, crop_x)
            crop_y = max(0, crop_y)
            crop_right = min(orig_width, crop_right)
            crop_bottom = min(orig_height, crop_bottom)
            if crop_right > crop_x and crop_bottom > crop_y:
                img = img.crop((crop_x, crop_y, crop_right, crop_bottom))
            else:
                logger.warning(f"Invalid crop dimensions for {image_data.get('src', 'unknown')}, skipping crop.")
        
        # Handle flip operations before resize
        if image_data.get('flipX', False):
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if image_data.get('flipY', False):
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        
        # Use config for special image types instead of hardcoded values
        is_background_image = image_data.get('id') in CONFIG['images']['background_identifiers']
        keep_ratio_json = image_data.get('keepRatio', True)
        
        # Get resampling quality from config
        resampling_quality = getattr(Image.Resampling, CONFIG['images']['default_quality'])
        
        if is_background_image:
            # Background: Scale to fit canvas height, maintaining aspect ratio
            canvas_height = CONFIG['canvas']['default_height']
            aspect_ratio = img.width / img.height
            new_height = canvas_height
            new_width = int(new_height * aspect_ratio)
            img = img.resize((new_width, new_height), resampling_quality)
        elif keep_ratio_json:
            # Non-background, keepRatio=True: Fit within element dimensions, maintain aspect ratio
            # Calculate new size preserving aspect ratio to fit within target_width/target_height
            original_aspect = img.width / img.height
            target_aspect = target_width / target_height

            if original_aspect > target_aspect:
                # Original is wider than target box: Fit to target_width
                new_width = target_width
                new_height = int(new_width / original_aspect)
            else:
                # Original is taller or same aspect as target box: Fit to target_height
                new_height = target_height
                new_width = int(new_height * original_aspect)

            # Ensure dimensions are at least 1x1
            new_width = max(1, new_width)
            new_height = max(1, new_height)

            logger.debug(f"Resizing image {image_data.get('id')} with keepRatio=True: original={img.size}, target_box=({target_width},{target_height}), new_size=({new_width},{new_height})")
            # Use resize which returns a new object
            img = img.resize((new_width, new_height), resampling_quality)
        else:
            # Non-background, keepRatio=False: Resize exactly to element dimensions (may distort)
            img = img.resize((target_width, target_height), resampling_quality)
        
        # Apply rotation (on the potentially smaller, aspect-preserved image)
        if image_data.get('rotation', 0) != 0:
            img = rotate_image(img, image_data.get('rotation', 0))
        
        # Apply corner radius
        if image_data.get('cornerRadius', 0) > 0:
            img = create_rounded_corners(img, image_data.get('cornerRadius', 0))
        
        # Apply various effects
        img = apply_image_effects(img, image_data)
        
        # Calculate position based on JSON
        x = int(image_data['x'])
        y = int(image_data['y'])
        
        return img, (x, y)
        
    except Exception as e:
        logger.error(f"Error processing image {image_data.get('src', 'unknown')}: {str(e)}")
        raise 