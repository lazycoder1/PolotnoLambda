"""
Figure renderer module.
Handles processing and rendering of various shapes and figures.
"""

import json
import io
import re # Use regex again
from pathlib import Path
from PIL import Image
# from lxml import etree # Remove lxml import
# from svglib.svglib import svg2rlg # Remove svglib imports
# from reportlab.graphics import renderPM
import cairosvg # Import cairosvg

from typing import Dict, Any, Tuple
from utils.helpers import parse_color, rgba_to_svg_rgba, hex_to_rgba_string
from image_processor.logger import get_logger

logger = get_logger(__name__)

# Load shape mapping (Load once)
SHAPE_MAPPING_PATH = Path(__file__).parent / "image_assets" / "shape_mapping.json"
SHAPE_SVG_DATA = {}
try:
    with open(SHAPE_MAPPING_PATH, 'r') as f:
        SHAPE_SVG_DATA = json.load(f)
    logger.info(f"Successfully loaded shape mapping from {SHAPE_MAPPING_PATH}")
except FileNotFoundError:
    logger.error(f"Shape mapping file not found at {SHAPE_MAPPING_PATH}")
except json.JSONDecodeError:
    logger.error(f"Error decoding JSON from {SHAPE_MAPPING_PATH}")
except Exception as e:
    logger.error(f"Error loading shape mapping: {e}")


def process_figure(figure_data: Dict[str, Any], image: Image.Image) -> None:
    """Process and draw figure elements using SVG rendering via cairosvg""" # Docstring updated
    element_id = figure_data.get('id', 'N/A')
    logger.debug(f"Processing figure ID: {element_id} using SVG rendering (cairosvg)") # Log updated
    
    try:
        # Validate input
        required_fields = ['x', 'y', 'width', 'height', 'subType']
        for field in required_fields:
            if field not in figure_data:
                raise ValueError(f"Missing required field '{field}' in figure data for ID {element_id}")
        
        # Get position and dimensions
        x = int(figure_data['x'])
        y = int(figure_data['y'])
        width = int(figure_data['width'])
        height = int(figure_data['height'])
        sub_type = figure_data['subType']

        # Ensure width and height are positive
        if width <= 0 or height <= 0:
            logger.warning(f"Figure ID {element_id} has non-positive dimensions ({width}x{height}). Skipping.")
            return
        
        # Get appearance properties
        fill_color_str = figure_data.get('fill', 'rgba(0,0,0,1)')
        stroke_color_str = figure_data.get('stroke', '#000000')
        stroke_width = figure_data.get('strokeWidth', 0)

        # Parse colors
        parsed_fill_color_tuple = parse_color(fill_color_str)
        if parsed_fill_color_tuple is None:
             logger.error(f"Invalid figure fill color format '{fill_color_str}' for ID {element_id}. Using default.")
             parsed_fill_color_tuple = (0, 0, 0, 255)
        if len(parsed_fill_color_tuple) == 3:
             parsed_fill_color_tuple = (*parsed_fill_color_tuple, 255)
        svg_fill_color = rgba_to_svg_rgba(parsed_fill_color_tuple)
        logger.debug(f"Parsed fill color for {element_id}: {svg_fill_color}")

        parsed_stroke_color_tuple = parse_color(stroke_color_str)
        # Use original hex for stroke if possible, otherwise convert rgba
        svg_stroke_color = "#000000" # Default stroke color if invalid
        if parsed_stroke_color_tuple:
             if isinstance(stroke_color_str, str) and stroke_color_str.startswith('#'):
                 svg_stroke_color = stroke_color_str # Keep hex if valid
             else: # Convert RGBA tuple to appropriate SVG color string
                 svg_stroke_color = rgba_to_svg_rgba(parsed_stroke_color_tuple)
        else:
            logger.warning(f"Invalid stroke color '{stroke_color_str}' for {element_id}, using default black.")
        logger.debug(f"Parsed stroke color for {element_id}: {svg_stroke_color}, width: {stroke_width}")

        # Check if sub_type exists in our SVG mapping
        if sub_type in SHAPE_SVG_DATA:
            svg_template = SHAPE_SVG_DATA[sub_type]
            
            # Modify SVG template with actual fill, stroke, and stroke-width using regex
            modified_svg = re.sub(r'fill="rgba\([^)]*\)"' , f'fill="{svg_fill_color}"' , svg_template)
            modified_svg = re.sub(r'stroke="#[0-9a-fA-F]{6}"' , f'stroke="{svg_stroke_color}"' , modified_svg)
            modified_svg = re.sub(r'stroke-width="[0-9.]*"' , f'stroke-width="{stroke_width}"' , modified_svg)
            
            # --- Add viewBox and preserveAspectRatio="none" to force scaling --- 
            # Add viewBox if not present (assuming base coordinate system is 0 0 300 300)
            if 'viewBox=' not in modified_svg:
                modified_svg = re.sub(r'<svg', '<svg viewBox="0 0 300 300"', modified_svg, count=1)
            # Remove specific width/height attributes
            modified_svg = re.sub(r' width="[0-9.]*"' , '' , modified_svg)
            modified_svg = re.sub(r' height="[0-9.]*"' , '' , modified_svg)
            # Add/replace preserveAspectRatio
            if 'preserveAspectRatio=' in modified_svg:
                 modified_svg = re.sub(r'preserveAspectRatio="[^"]*"' , 'preserveAspectRatio="none"' , modified_svg)
            else:
                 modified_svg = re.sub(r'<svg', '<svg preserveAspectRatio="none"', modified_svg, count=1)
            # ------------------------------------------------------------------

            logger.debug(f"Modified SVG for {element_id} via regex: {modified_svg[:300]}...") # Log more to see changes

            # Render SVG to PNG bytes using cairosvg
            try:
                png_bytes = cairosvg.svg2png(
                    bytestring=modified_svg.encode('utf-8'), 
                    output_width=width, 
                    output_height=height
                )
            except Exception as svg_err:
                 logger.error(f"CairoSVG error rendering {sub_type} for ID {element_id}: {svg_err}")
                 # Fallback: draw a placeholder rectangle
                 from PIL import ImageDraw # Import only if needed
                 draw_fallback = ImageDraw.Draw(image)
                 draw_fallback.rectangle([x, y, x + width, y + height], outline="red", width=2)
                 logger.info(f"Drew fallback rectangle for failed SVG {element_id}")
                 return

            # Load PNG bytes into a PIL Image
            svg_image = Image.open(io.BytesIO(png_bytes))

            # --- DEBUG: Save intermediate SVG render ---
            try:
                debug_filename = f"debug_svg_{element_id}_{sub_type}.png"
                svg_image.save(debug_filename)
                logger.info(f"Saved intermediate SVG render for {element_id} to {debug_filename}")
            except Exception as save_err:
                logger.error(f"Could not save debug SVG image for {element_id}: {save_err}")
            # --- END DEBUG ---

            # Paste the SVG image onto the main image using alpha compositing
            if svg_image.mode != 'RGBA':
                 svg_image = svg_image.convert('RGBA')
                 
            # Create a mask from the alpha channel for proper pasting
            if 'A' in svg_image.getbands():
                mask = svg_image.split()[3] 
            else:
                logger.warning(f"Rendered SVG {element_id} has no alpha channel. Pasting without mask.")
                mask = None
            
            image.paste(svg_image, (x, y), mask=mask)
            logger.debug(f"Successfully rendered and pasted SVG '{sub_type}' for ID {element_id} at ({x},{y}) size {width}x{height}")

        else:
            # Fallback for shapes not in mapping (including original rect/ellipse/circle)
            logger.warning(f"SVG not found for shape '{sub_type}' (ID: {element_id}). Attempting direct draw.")
            # --- Fallback Drawing Code --- 
            from PIL import ImageDraw # Import only if needed
            draw_fallback = ImageDraw.Draw(image)
            coords = [x, y, x + width, y + height]
            # Re-parse fill color tuple for Pillow
            fill_tuple_pillow = parse_color(fill_color_str, default_color=(0,0,0,0))
            # Re-parse stroke color tuple for Pillow
            stroke_tuple_pillow = None
            if stroke_width > 0:
                    stroke_tuple_pillow = parse_color(stroke_color_str, default_color=None)
            
            logger.debug(f"Fallback drawing {sub_type} ID: {element_id} Fill: {fill_tuple_pillow} Stroke: {stroke_tuple_pillow} Width: {stroke_width}")
            
            if sub_type == 'rect':
                corner_radius = figure_data.get('cornerRadius', 0)
                if corner_radius > 0:
                    draw_fallback.rounded_rectangle(coords, radius=corner_radius, fill=fill_tuple_pillow, outline=stroke_tuple_pillow, width=stroke_width)
                else:
                    draw_fallback.rectangle(coords, fill=fill_tuple_pillow, outline=stroke_tuple_pillow, width=stroke_width)
            elif sub_type == 'ellipse' or sub_type == 'circle':
                draw_fallback.ellipse(coords, fill=fill_tuple_pillow, outline=stroke_tuple_pillow, width=stroke_width)
            else:
                logger.warning(f"Unsupported figure subType '{sub_type}' for fallback drawing (ID: {element_id}). Skipping.")
            # --- End Fallback --- 
                
    except ValueError as ve:
         logger.error(f"Data validation error for figure ID {element_id}: {ve}")
    except Exception as e:
        logger.error(f"Error processing figure ID {element_id}: {e}", exc_info=True) 