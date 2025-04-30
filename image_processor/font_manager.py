"""
Font management module for the image processor.
Handles font discovery, loading, selection, and Devanagari script detection.
"""

import os
import re
import logging
from collections import defaultdict
from typing import Dict, Tuple, Optional, Any
from PIL import ImageFont
import json # Keep for debug logging if needed
from utils.helpers import contains_devanagari # Import from helpers
from .config import CONFIG # <--- Import CONFIG

# Setup logger for this module
logger = logging.getLogger(__name__)

# Constants
FONT_DIR = 'fonts'
# DEVANAGARI_FAMILY = 'notosansdevanagari' # <-- Remove hardcoded constant
WEIGHT_KEYWORDS = {'thin', 'extralight', 'light', 'regular', 'medium', 'semibold', 'bold', 'extrabold', 'black', 'heavy'}
STYLE_KEYWORDS = {'italic', 'oblique'}
NORMAL_WEIGHTS = {'normal', 'regular'} # Treat regular as normal

class FontManager:
    """
    Manages available fonts, providing selection logic based on text properties.

    Attributes:
        _font_map (Optional[Dict]): Lazily loaded map of available fonts.
                                     Structure: {family_lower: {style_weight_lower: path}}
        _default_font (Optional[ImageFont.FreeTypeFont]): Lazily loaded default Pillow font.
    """
    _font_map: Optional[Dict[str, Dict[str, str]]] = None
    _default_font: Optional[ImageFont.FreeTypeFont] = None

    # --- Public API ---

    @classmethod
    def select_font(cls, text_data: Dict[str, Any], font_size: int) -> Tuple[Optional[ImageFont.FreeTypeFont], str]:
        """
        Selects the appropriate font based on text properties and language.

        Checks for Devanagari script and prioritizes the DEVANAGARI_FAMILY.
        Falls back to requested font, then default font.

        NOTE: For complex scripts like Devanagari, ensure 'libraqm' library is
              installed and accessible by Pillow for proper rendering of conjuncts.
              Check Pillow documentation for enabling Raqm support. Run:
              `from PIL import features; print(features.check('raqm'))`

        Args:
            text_data: Dictionary containing text properties like 'text',
                       'fontFamily', 'fontWeight', 'fontStyle'.
            font_size: The desired font size.

        Returns:
            A tuple containing the loaded PIL ImageFont object (or None)
            and a string describing the font source (e.g., "map (family weight)", "default").
        """
        text = text_data.get('text', '')
        if not text:
            return None, "empty text"

        req_family = text_data.get('fontFamily', 'Arial').lower()
        req_weight = text_data.get('fontWeight', 'normal').lower()
        req_style = text_data.get('fontStyle', 'normal').lower()

        # Normalize weight aliases
        if req_weight in NORMAL_WEIGHTS:
            req_weight = 'normal'

        font = None
        font_path = None
        source_info = "unknown"

        # 1. Check for Devanagari script
        if contains_devanagari(text):
            preferred_dev_family = CONFIG['fonts'].get('primary_devanagari_family', 'notosansdevanagari').lower()
            logger.debug(f"Devanagari detected in '{text[:20]}...'. Prioritizing '{preferred_dev_family}'.")
            font_path = cls._find_font_path(preferred_dev_family, req_weight, 'normal') # Devanagari fonts usually aren't italic
            if font_path:
                font = cls._load_font(font_path, font_size)
                if font:
                    # Extract actual weight/style from path for better source info
                    found_weight_style = cls._extract_weight_style_from_path(font_path, req_weight)
                    source_info = f"map ({preferred_dev_family} {found_weight_style})"
                    return font, source_info
                else:
                    logger.warning(f"Found Devanagari font path '{font_path}' but failed to load.")
            else:
                logger.warning(f"Devanagari detected, but no suitable font found for family '{preferred_dev_family}'.")

        # 2. Try requested font family/weight/style if Devanagari not needed or not found
        if font is None:
            logger.debug(f"Attempting requested font: Family='{req_family}', Weight='{req_weight}', Style='{req_style}'")
            font_path = cls._find_font_path(req_family, req_weight, req_style)
            if font_path:
                font = cls._load_font(font_path, font_size)
                if font:
                    found_weight_style = cls._extract_weight_style_from_path(font_path, f"{req_weight}-{req_style}" if req_style != 'normal' else req_weight)
                    source_info = f"map ({req_family} {found_weight_style})"
                    return font, source_info
                else:
                    logger.warning(f"Found requested font path '{font_path}' but failed to load.")

        # 3. Fallback to default font
        if font is None:
            logger.warning(f"Could not find/load specific font for: Family='{req_family}', Weight='{req_weight}', Style='{req_style}'. Falling back to default.")
            default_font = cls.get_default_font()
            if default_font:
                return default_font, "Pillow default"
            else:
                logger.error("Failed to load even the default Pillow font.")
                return None, "error loading default"

        # Should technically not be reached if default font logic works
        return font, source_info

    @staticmethod
    def contains_devanagari(text: str) -> bool:
        """
        Checks if the text contains characters in the Devanagari Unicode range.

        Args:
            text: The string to check.

        Returns:
            True if Devanagari characters are found, False otherwise.
        """
        # Devanagari range: U+0900 to U+097F
        for char in text:
            if '\u0900' <= char <= '\u097F':
                return True
        return False

    # --- Internal Helpers & Initialization ---

    @classmethod
    def get_font_map(cls) -> Dict[str, Dict[str, str]]:
        """
        Gets the font map, building it on first access.

        Returns:
            The font map dictionary.
        """
        if cls._font_map is None:
            cls._build_font_map()
        # Ensure _font_map is not None after build attempt, return empty if build failed
        return cls._font_map if cls._font_map is not None else {}

    @classmethod
    def get_default_font(cls) -> Optional[ImageFont.FreeTypeFont]:
        """
        Gets the default Pillow font, loading it on first access.

        Returns:
            The default ImageFont object or None if loading fails.
        """
        if cls._default_font is None:
            try:
                logger.debug("Loading Pillow default font.")
                cls._default_font = ImageFont.load_default()
            except Exception as e:
                logger.error(f"Failed to load Pillow default font: {e}")
                cls._default_font = None # Ensure it remains None on failure
        return cls._default_font

    @classmethod
    def _build_font_map(cls) -> None:
        """
        Scans the FONT_DIR directory and builds the _font_map cache.
        Prioritizes the DEVANAGARI_FAMILY subdirectory.
        """
        logger.info(f"Building font map from directory: '{FONT_DIR}'")
        cls._font_map = defaultdict(dict)
        if not os.path.isdir(FONT_DIR):
            logger.error(f"Font directory '{FONT_DIR}' not found. Cannot build font map.")
            return

        preferred_dev_family = CONFIG['fonts'].get('primary_devanagari_family', 'notosansdevanagari').lower()

        scan_order = []
        # 1. Prioritize Devanagari directory if it exists
        devanagari_path = os.path.join(FONT_DIR, preferred_dev_family)
        if os.path.isdir(devanagari_path):
            logger.debug(f"Prioritizing scan of: '{devanagari_path}'")
            scan_order.append(devanagari_path)

        # 2. Add other top-level items from FONT_DIR
        for item in os.listdir(FONT_DIR):
            item_path = os.path.join(FONT_DIR, item)
            # Add if it's a file or a directory not already prioritized
            if item_path not in scan_order and (os.path.isfile(item_path) or os.path.isdir(item_path)):
                 scan_order.append(item_path)

        # 3. Scan paths in defined order
        found_count = 0
        processed_files = set() # Avoid processing duplicates if structure is odd
        for path_to_scan in scan_order:
             if os.path.isdir(path_to_scan):
                 for root, _, files in os.walk(path_to_scan):
                     for filename in files:
                         if filename.lower().endswith('.ttf'):
                            file_path = os.path.join(root, filename)
                            if file_path not in processed_files:
                                if cls._parse_and_add_font(file_path):
                                     found_count += 1
                                processed_files.add(file_path)
             elif os.path.isfile(path_to_scan) and path_to_scan.lower().endswith('.ttf'):
                 if path_to_scan not in processed_files:
                     if cls._parse_and_add_font(path_to_scan):
                         found_count += 1
                     processed_files.add(path_to_scan)


        logger.info(f"Font map build complete. Found {found_count} unique font files.")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Built Font Map:\n{json.dumps(cls._font_map, indent=2)}")


    @classmethod
    def _parse_and_add_font(cls, file_path: str) -> bool:
        """
        Parses font filename to determine family, weight, and style, then adds to map.

        Args:
            file_path: The full path to the font file.

        Returns:
            True if font was successfully parsed and added, False otherwise.
        """
        try:
            filename = os.path.basename(file_path)
            base_name = os.path.splitext(filename)[0]

            # Simple parsing: split by common separators, identify keywords
            parts = re.split(r'[-_ ]', base_name)
            family_parts = []
            found_weight = 'normal'
            found_style = 'normal'

            # Iterate backwards to find style/weight keywords first
            remaining_parts = parts[:]
            for part in reversed(parts):
                part_lower = part.lower()
                if part_lower in STYLE_KEYWORDS:
                    if found_style == 'normal': # Keep first style found (e.g., Italic over Oblique if both present)
                         found_style = part_lower
                    remaining_parts.pop()
                elif part_lower in WEIGHT_KEYWORDS:
                    if found_weight == 'normal': # Keep first weight found
                        found_weight = part_lower
                    remaining_parts.pop()
                elif found_style != 'normal' and found_weight != 'normal':
                     # Stop if we already found both, remaining must be family
                     break

            # Normalize weight
            if found_weight in NORMAL_WEIGHTS:
                 found_weight = 'normal'

            # Construct family name from remaining parts
            family_name = "".join(remaining_parts) if remaining_parts else base_name # Fallback to base if parsing fails
            family_lower = family_name.lower()

            # Generate style key (e.g., "normal", "bold", "normal-italic", "bold-italic")
            style_key = found_weight
            if found_style != 'normal':
                style_key = f"{found_weight}-{found_style}"

            if family_lower and style_key:
                # Special handling for prioritized Devanagari family
                preferred_dev_family_from_config = CONFIG['fonts'].get('primary_devanagari_family', '').lower()
                # If a specific devanagari family is configured AND the parsed family name contains it,
                # use the configured name as the key. Otherwise, use the parsed name.
                map_family_key = preferred_dev_family_from_config \
                    if preferred_dev_family_from_config and preferred_dev_family_from_config in family_lower \
                    else family_lower

                if style_key not in cls._font_map[map_family_key]:
                    cls._font_map[map_family_key][style_key] = file_path
                    logger.debug(f"Mapped: '{filename}' -> Family: '{map_family_key}', StyleKey: '{style_key}', Path: '{file_path}'")

                    # Add alias for regular -> normal if it's a normal weight font
                    if found_weight == 'normal' and found_style == 'normal' and 'regular' not in cls._font_map[map_family_key]:
                         cls._font_map[map_family_key]['regular'] = file_path # Alias regular to normal path
                    return True
                else:
                    logger.debug(f"Skipping duplicate style key '{style_key}' for family '{map_family_key}'. Existing path: '{cls._font_map[map_family_key][style_key]}'")
                    return False
            else:
                 logger.warning(f"Could not parse family/style from font filename: '{filename}'")
                 return False

        except Exception as e:
            logger.error(f"Error parsing font file '{file_path}': {e}")
            return False


    @classmethod
    def _find_font_path(cls, family_lower: str, weight_lower: str, style_lower: str) -> Optional[str]:
        """
        Finds the font path in the map with fallback logic.

        Fallback Order:
        1. Exact match (e.g., bold-italic)
        2. Weight match, normal style (e.g., bold)
        3. Normal weight, exact style (e.g., normal-italic)
        4. Normal weight, normal style (e.g., normal)
        5. Any available style/weight for the family.

        Args:
            family_lower: Lowercase font family name.
            weight_lower: Lowercase font weight ('normal', 'bold', etc.).
            style_lower: Lowercase font style ('normal', 'italic').

        Returns:
            The font file path string, or None if not found.
        """
        font_map = cls.get_font_map()
        if family_lower not in font_map:
            return None

        family_styles = font_map[family_lower]

        # Determine target style key (e.g., "bold-italic" or "bold")
        target_key = weight_lower
        if style_lower != 'normal':
            target_key = f"{weight_lower}-{style_lower}"

        # Fallback keys in order of preference
        fallback_keys = [
            target_key,                             # 1. Exact match
            weight_lower,                           # 2. Weight match, normal style
        ]
        if style_lower != 'normal':               # 3. Normal weight, exact style (if italic requested)
             fallback_keys.append(f"normal-{style_lower}")
        fallback_keys.append("normal")              # 4. Normal weight, normal style

        # Try fallbacks
        for key in fallback_keys:
            if key in family_styles:
                logger.debug(f"Found font path for '{family_lower}' using key '{key}'.")
                return family_styles[key]

        # 5. Any available style as last resort
        if family_styles:
            first_available_key = next(iter(family_styles))
            logger.debug(f"No specific match for '{family_lower}' '{target_key}'. Falling back to first available: '{first_available_key}'.")
            return family_styles[first_available_key]

        logger.warning(f"No font files found in map for family '{family_lower}'.")
        return None

    @staticmethod
    def _load_font(path: str, size: int) -> Optional[ImageFont.FreeTypeFont]:
        """Loads a font file using PIL, handling errors."""
        if not path or not os.path.exists(path):
            logger.error(f"Font path is invalid or file does not exist: '{path}'")
            return None
        try:
            font = ImageFont.truetype(path, size)
            logger.debug(f"Successfully loaded font: '{path}' size: {size}")
            return font
        except Exception as e:
            logger.error(f"Failed to load font '{path}' with size {size}: {e}")
            return None

    @staticmethod
    def _extract_weight_style_from_path(path: str, default: str = "unknown") -> str:
        """Helper to guess weight/style from path for logging - crude."""
        try:
            basename = os.path.splitext(os.path.basename(path))[0].lower()
            parts = re.split(r'[-_ ]', basename)
            style = next((p for p in parts if p in STYLE_KEYWORDS), "normal")
            weight = next((p for p in parts if p in WEIGHT_KEYWORDS or p in NORMAL_WEIGHTS), "normal")
            if weight in NORMAL_WEIGHTS: weight = "normal"
            key = weight
            if style != 'normal':
                 key = f"{weight}-{style}"
            return key
        except:
            return default

# Example usage (optional, for testing)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG) # Enable debug logging for testing

    # Test Devanagari check
    print(f"Contains Devanagari ('नमस्ते'): {contains_devanagari('नमस्ते')}")
    print(f"Contains Devanagari ('Hello'): {contains_devanagari('Hello')}")

    # Build and show the map
    font_map = FontManager.get_font_map()
    # print("Font Map:", font_map) # Already printed by logger in debug mode

    # Example text data
    test_text_data_dev = {'text': 'अल्ट्रासॉफ्ट', 'fontFamily': 'Arial', 'fontWeight': 'bold'}
    test_text_data_eng = {'text': 'Hello World', 'fontFamily': 'Raleway', 'fontWeight': 'bold', 'fontStyle': 'italic'}
    test_text_data_fallback = {'text': 'Fallback Test', 'fontFamily': 'NonExistentFont', 'fontWeight': 'normal'}

    # Select fonts
    font_dev, source_dev = FontManager.select_font(test_text_data_dev, 30)
    print(f"Devanagari Font: {font_dev.path if font_dev else 'None'}, Source: {source_dev}")

    font_eng, source_eng = FontManager.select_font(test_text_data_eng, 30)
    print(f"English Font: {font_eng.path if font_eng else 'None'}, Source: {source_eng}")

    font_fall, source_fall = FontManager.select_font(test_text_data_fallback, 30)
    print(f"Fallback Font: {font_fall.path if font_fall else 'None'}, Source: {source_fall}")

    # Check default font caching
    print("Getting default font again...")
    default_font = FontManager.get_default_font()
    print(f"Default Font (again): {default_font.path if default_font else 'None'}") 