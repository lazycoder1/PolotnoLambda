import json
import os
from typing import Dict, Any, Tuple, Optional
import re # Add re import
import logging # Import logging

logger = logging.getLogger(__name__) # Setup logger for helpers

# --- NEW: Add basic color name mapping ---
COLOR_NAME_MAP = {
    "white": (255, 255, 255, 255),
    "black": (0, 0, 0, 255),
    "red": (255, 0, 0, 255),
    "green": (0, 128, 0, 255), # Using standard green, not lime
    "blue": (0, 0, 255, 255),
    "yellow": (255, 255, 0, 255),
    "cyan": (0, 255, 255, 255),
    "magenta": (255, 0, 255, 255),
    "silver": (192, 192, 192, 255),
    "gray": (128, 128, 128, 255),
    "grey": (128, 128, 128, 255),
    "maroon": (128, 0, 0, 255),
    "olive": (128, 128, 0, 255),
    "purple": (128, 0, 128, 255),
    "teal": (0, 128, 128, 255),
    "navy": (0, 0, 128, 255),
    "transparent": (0, 0, 0, 0) # Useful alias
    # Add more names as needed
}
# ---------------------------------------

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

def parse_color(color_input: Any, default_color: Optional[Tuple[int, int, int, int]] = (0, 0, 0, 255)) -> Optional[Tuple[int, int, int, int]]:
    """Parses a color input (hex, rgb, rgba, name string, or tuple) into an RGBA tuple."""
    
    # --- MODIFIED: Handle direct tuple/list input --- 
    if isinstance(color_input, (tuple, list)):
        if len(color_input) == 4 and all(isinstance(c, int) for c in color_input):
            # Assume valid RGBA tuple
            r, g, b, a = color_input
            # Clamp values just in case
            return (
                max(0, min(255, r)),
                max(0, min(255, g)),
                max(0, min(255, b)),
                max(0, min(255, a))
            )
        elif len(color_input) == 3 and all(isinstance(c, int) for c in color_input):
             # Assume valid RGB tuple, add full alpha
            r, g, b = color_input
            return (
                max(0, min(255, r)),
                max(0, min(255, g)),
                max(0, min(255, b)),
                255
            )
        else:
             logger.warning(f"Invalid tuple/list format for color: {color_input}. Using default.")
             return default_color
             
    # --- Ensure input is string for further parsing --- 
    if not isinstance(color_input, str):
        logger.warning(f"Invalid color type provided: {type(color_input)}. Expected string or tuple/list. Using default.")
        return default_color

    color_str = color_input.strip().lower()

    # --- NEW: Try parsing Color Name --- 
    if color_str in COLOR_NAME_MAP:
        logger.debug(f"Parsed color name '{color_str}' -> {COLOR_NAME_MAP[color_str]}")
        return COLOR_NAME_MAP[color_str]
    # ---------------------------------

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

def rgba_to_svg_rgba(rgba_tuple: Tuple[int, int, int, int]) -> str:
    """Converts an RGBA tuple (0-255) to an SVG rgba string (alpha 0.0-1.0)."""
    if not (isinstance(rgba_tuple, tuple) and len(rgba_tuple) == 4 and all(isinstance(c, int) for c in rgba_tuple)):
        logger.warning(f"Invalid RGBA tuple for SVG conversion: {rgba_tuple}. Using default black.")
        return "rgba(0,0,0,1.0)"
    r, g, b, a = rgba_tuple
    # Clamp values just in case
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    a_float = round(max(0, min(255, a)) / 255.0, 4) # Convert alpha to 0.0-1.0 and round
    return f"rgba({r},{g},{b},{a_float})"

def hex_to_rgba_string(hex_color: str) -> Optional[str]:
    """Converts a hex color string (#RRGGBB or #RRGGBBAA) to an SVG rgba string."""
    if not isinstance(hex_color, str) or not hex_color.startswith('#'):
        return None
    hex_val = hex_color.lstrip('#')
    try:
        if len(hex_val) == 6:
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
            return f"rgba({r},{g},{b},1.0)" # Full opacity
        elif len(hex_val) == 8:
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
            a = int(hex_val[6:8], 16)
            a_float = round(a / 255.0, 4)
            return f"rgba({r},{g},{b},{a_float})"
        else:
            return None # Invalid length
    except ValueError:
        return None # Invalid hex characters 