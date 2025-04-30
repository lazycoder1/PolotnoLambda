import json
import os
from typing import Dict, Any, Tuple, Optional
import re # Add re import
import logging # Import logging

logger = logging.getLogger(__name__) # Setup logger for helpers

def contains_devanagari(text: str) -> bool:
    """Check if the text contains characters in the Devanagari Unicode range."""
    # Devanagari range: U+0900 to U+097F
    if not isinstance(text, str): # Add type check
        return False
    for char in text:
        if '\u0900' <= char <= '\u097F':
            return True
    return False

def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load JSON data from a file"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"JSON file not found: {file_path}")
    
    with open(file_path, 'r') as f:
        return json.load(f)

def save_image(image, output_path: str):
    """Save image to specified path"""
    image.save(output_path)
    return output_path

def validate_json_structure(json_data: Dict[str, Any]) -> bool:
    """Validate the structure of the JSON data"""
    required_fields = ['width', 'height', 'pages']
    if not all(field in json_data for field in required_fields):
        return False
    
    if not isinstance(json_data['pages'], list):
        return False
    
    for page in json_data['pages']:
        if 'children' not in page or not isinstance(page['children'], list):
            return False
    
    return True 

def parse_color(color_str: str, default_color: Tuple[int, int, int, int] = (0, 0, 0, 255)) -> Tuple[int, int, int, int]:
    """Parses a color string (hex, rgb, rgba) into an RGBA tuple."""
    if not isinstance(color_str, str):
        logger.warning(f"Invalid color type provided: {type(color_str)}. Using default.")
        return default_color

    color_str = color_str.strip().lower()

    # Try parsing HEX (#RRGGBB or #RRGGBBAA)
    if color_str.startswith('#'):
        hex_val = color_str[1:]
        logger.debug(f"Attempting HEX parse for: {color_str}")
        try:
            if len(hex_val) == 6:
                r = int(hex_val[0:2], 16)
                g = int(hex_val[2:4], 16)
                b = int(hex_val[4:6], 16)
                return (r, g, b, 255)
            elif len(hex_val) == 8:
                r = int(hex_val[0:2], 16)
                g = int(hex_val[2:4], 16)
                b = int(hex_val[4:6], 16)
                a = int(hex_val[6:8], 16)
                return (r, g, b, a)
        except ValueError:
            logger.warning(f"Invalid hex color format: '{color_str}'. Using default.")
            return default_color

    # Try parsing rgba(r, g, b, a)
    rgba_match = re.match(r'rgba\(\s*(\d+%?)\s*,\s*(\d+%?)\s*,\s*(\d+%?)\s*,\s*(\d*[.]?\d+)\s*\)', color_str)
    logger.debug(f"Attempting RGBA parse for: {color_str}, Match: {bool(rgba_match)}")
    if rgba_match:
        try:
            r_str, g_str, b_str, a_str = rgba_match.groups()
            logger.debug(f"RGBA Groups: r='{r_str}', g='{g_str}', b='{b_str}', a='{a_str}'")
            r = int(r_str.rstrip('%'))
            g = int(g_str.rstrip('%'))
            b = int(b_str.rstrip('%'))
            a = float(a_str) # Alpha is 0.0 to 1.0
            # Clamp values
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            a_int = int(max(0.0, min(1.0, a)) * 255)
            logger.debug(f"RGBA Parsed Tuple: ({r}, {g}, {b}, {a_int})")
            return (r, g, b, a_int)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid rgba color format: '{color_str}'. Error: {e}. Using default.")
            logger.debug(f"Returning default color: {default_color}")
            return default_color

    # Try parsing rgb(r, g, b)
    rgb_match = re.match(r'rgb\(\s*(\d+%?)\s*,\s*(\d+%?)\s*,\s*(\d+%?)\s*\)', color_str)
    logger.debug(f"Attempting RGB parse for: {color_str}, Match: {bool(rgb_match)}")
    if rgb_match:
        try:
            r_str, g_str, b_str = rgb_match.groups()
            logger.debug(f"RGB Groups: r='{r_str}', g='{g_str}', b='{b_str}'")
            r = int(r_str.rstrip('%'))
            g = int(g_str.rstrip('%'))
            b = int(b_str.rstrip('%'))
            # Clamp values
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            logger.debug(f"RGB Parsed Tuple: ({r}, {g}, {b}, 255)")
            return (r, g, b, 255) # Return RGBA with full opacity
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid rgb color format: '{color_str}'. Error: {e}. Using default.")
            logger.debug(f"Returning default color: {default_color}")
            return default_color

    # If no format matches
    logger.debug(f"No color format matched for: {color_str}")
    logger.warning(f"Unrecognized color format: '{color_str}'. Using default.")
    logger.debug(f"Returning default color: {default_color}")
    return default_color 