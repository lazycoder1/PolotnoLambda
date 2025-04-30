import json
import os
from typing import Dict, Any, Tuple, Optional
import re # Add re import

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

def parse_color(color_string: str) -> Optional[str]:
    """Parse various color string formats and return a hex color string (#RRGGBB or #RRGGBBAA)."""
    color_string = color_string.strip().lower()
    
    r, g, b, a = -1, -1, -1, 255 # Default alpha to opaque
    
    # Hex codes (#rgb, #rrggbb, #rrggbbaa)
    if color_string.startswith('#'):
        hex_color = color_string[1:]
        if len(hex_color) == 3: # rgb
            r, g, b = [int(c * 2, 16) for c in hex_color]
            a = 255
        elif len(hex_color) == 6: # rrggbb
            r, g, b = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
            a = 255
        elif len(hex_color) == 8: # rrggbbaa
            r, g, b, a = [int(hex_color[i:i+2], 16) for i in (0, 2, 4, 6)]
            
    # rgba(r, g, b, a) - alpha 0.0-1.0
    match_rgba = re.match(r'rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)', color_string)
    if match_rgba:
        r, g, b = map(int, match_rgba.groups()[:3])
        a_float = float(match_rgba.group(4))
        a = int(max(0, min(1, a_float)) * 255) # Clamp alpha 0-1 and convert to 0-255
        
    # rgb(r, g, b)
    match_rgb = re.match(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', color_string)
    if match_rgb:
        r, g, b = map(int, match_rgb.groups())
        a = 255
        
    # Simple color names 
    simple_colors = {
        'black': (0, 0, 0, 255),
        'white': (255, 255, 255, 255),
        'red': (255, 0, 0, 255),
        'green': (0, 128, 0, 255),
        'blue': (0, 0, 255, 255),
        'transparent': (0, 0, 0, 0)
    }
    if color_string in simple_colors:
        r, g, b, a = simple_colors[color_string]
        
    # Check if any parsing succeeded and values are valid
    if all(0 <= val <= 255 for val in [r, g, b, a]) and r != -1:
         # Format as hex
         if a == 255:
             return f"#{r:02x}{g:02x}{b:02x}".upper()
         else:
             return f"#{r:02x}{g:02x}{b:02x}{a:02x}".upper()
    else:
        # Could not parse or invalid values found
        print(f"Warning: Could not parse color '{color_string}' into valid RGBA.")
        return None # Indicate failure to parse 