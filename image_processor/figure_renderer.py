"""
Figure renderer module.
Handles processing and rendering of various shapes and figures.
"""

import json
import io
import re # Use regex again
from pathlib import Path
from PIL import Image, ImageDraw
# from lxml import etree # Remove lxml import
# from svglib.svglib import svg2rlg # Remove svglib imports
# from reportlab.graphics import renderPM
import cairosvg # Import cairosvg

from typing import Dict, Any, Tuple, Optional
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


def render_figure_to_image(figure_data: Dict[str, Any]) -> Optional[Image.Image]:
    """
    Processes and renders a figure element to its own PIL Image layer,
    using the documented scaling and cropping approach:
    1. Determine constrained dimension
    2. Calculate target dimensions
    3. Scale figure proportionally
    4. Apply cropping
    """
    element_id = figure_data.get('id', 'N/A')
    logger.debug(f"Rendering figure ID: {element_id} to its own layer.")

    try:
        required_fields = ['width', 'height', 'subType'] # x, y are used by the main processor
        for field in required_fields:
            if field not in figure_data:
                raise ValueError(f"Missing required field '{field}' in figure data for ID {element_id}")

        final_width = int(figure_data['width'])
        final_height = int(figure_data['height'])
        sub_type = figure_data['subType']

        if final_width <= 0 or final_height <= 0:
            logger.warning(f"Figure ID {element_id} has non-positive dimensions ({final_width}x{final_height}). Returning None.")
            return None

        fill_color_str = figure_data.get('fill', 'rgba(0,0,0,1)')
        stroke_color_str = figure_data.get('stroke', '#000000')
        stroke_width = figure_data.get('strokeWidth', 0)

        parsed_fill_color_tuple = parse_color(fill_color_str)
        if parsed_fill_color_tuple is None:
            logger.error(f"Invalid figure fill color '{fill_color_str}' for ID {element_id}. Defaulting.")
            parsed_fill_color_tuple = (0, 0, 0, 255)
        if len(parsed_fill_color_tuple) == 3:
            parsed_fill_color_tuple = (*parsed_fill_color_tuple, 255)
        svg_fill_color = rgba_to_svg_rgba(parsed_fill_color_tuple)

        parsed_stroke_color_tuple = parse_color(stroke_color_str)
        svg_stroke_color = "#000000"
        if parsed_stroke_color_tuple:
            if isinstance(stroke_color_str, str) and stroke_color_str.startswith('#'):
                svg_stroke_color = stroke_color_str
            else:
                svg_stroke_color = rgba_to_svg_rgba(parsed_stroke_color_tuple)
        else:
            logger.warning(f"Invalid stroke color '{stroke_color_str}' for {element_id}. Defaulting to black.")

        # Get crop parameters
        crop_x = figure_data.get('cropX', 0.0)
        crop_y = figure_data.get('cropY', 0.0)
        crop_width = figure_data.get('cropWidth', 1.0)
        crop_height = figure_data.get('cropHeight', 1.0)
        
        # Calculate target dimensions based on our documented approach
        target_width = 0
        target_height = 0
        
        # Determine which dimension is constrained
        if crop_width < 1.0 and crop_height == 1.0:
            # Width-constrained calculation
            target_width = int(round(final_width / crop_width))
            # For figures, we maintain the aspect ratio if the original is a square or circle
            target_height = target_width if final_width == final_height else final_height
            logger.info(f"Width-constrained crop: Target dimensions {target_width}x{target_height}")
        elif crop_height < 1.0 and crop_width == 1.0:
            # Height-constrained calculation
            target_height = int(round(final_height / crop_height))
            # For figures, we maintain the aspect ratio if the original is a square or circle
            target_width = target_height if final_width == final_height else final_width
            logger.info(f"Height-constrained crop: Target dimensions {target_width}x{target_height}")
        elif crop_width < 1.0 and crop_height < 1.0:
            # Both dimensions constrained - calculate both and use the larger constraint
            width_target = int(round(final_width / crop_width))
            height_target = int(round(final_height / crop_height))
            
            if (final_width == final_height):
                # For square/circle figures, use the larger dimension to ensure both constraints are met
                target_dimension = max(width_target, height_target)
                target_width = target_dimension
                target_height = target_dimension
                logger.info(f"Both constrained (square figure): Target dimensions {target_width}x{target_height}")
            else:
                # For non-square figures, handle each dimension independently
                target_width = width_target
                target_height = height_target
                logger.info(f"Both constrained (non-square figure): Target dimensions {target_width}x{target_height}")
        else:
            # Neither dimension is constrained, use the final dimensions directly
            target_width = final_width
            target_height = final_height
            logger.info(f"No crop constraints: Target dimensions {target_width}x{target_height}")
        
        # Render the figure at the calculated dimensions
        if sub_type in SHAPE_SVG_DATA:
            svg_template = SHAPE_SVG_DATA[sub_type]
            modified_svg = re.sub(r'fill="rgba\([^)]*\)"' , f'fill="{svg_fill_color}"' , svg_template)
            modified_svg = re.sub(r'stroke="#[0-9a-fA-F]{6}"' , f'stroke="{svg_stroke_color}"' , modified_svg)
            modified_svg = re.sub(r'stroke-width="[0-9.]*"' , f'stroke-width="{stroke_width}"' , modified_svg)

            if 'viewBox=' not in modified_svg:
                modified_svg = re.sub(r'<svg', '<svg viewBox="0 0 300 300"', modified_svg, count=1)
            modified_svg = re.sub(r' width="[0-9.]*"' , '' , modified_svg)
            modified_svg = re.sub(r' height="[0-9.]*"' , '' , modified_svg)
            if 'preserveAspectRatio=' in modified_svg:
                modified_svg = re.sub(r'preserveAspectRatio="[^"]*"' , 'preserveAspectRatio="none"' , modified_svg)
            else:
                modified_svg = re.sub(r'<svg', '<svg preserveAspectRatio="none"', modified_svg, count=1)

            logger.debug(f"Rendering SVG for {element_id} (type {sub_type}) with cairosvg to {target_width}x{target_height}")
            try:
                png_bytes = cairosvg.svg2png(
                    bytestring=modified_svg.encode('utf-8'), 
                    output_width=target_width, 
                    output_height=target_height
                )
                scaled_figure = Image.open(io.BytesIO(png_bytes))
                if scaled_figure.mode != 'RGBA': # Ensure alpha channel for consistency
                    scaled_figure = scaled_figure.convert('RGBA')
            except Exception as svg_err:
                logger.error(f"CairoSVG error rendering {sub_type} for ID {element_id}: {svg_err}. Returning None.")
                return None # Failed to render SVG

        else:
            logger.debug(f"Figure type '{sub_type}' (ID: {element_id}) not in SVG mapping. Attempting direct draw on local canvas.")
            local_canvas = Image.new('RGBA', (target_width, target_height), (0,0,0,0)) # Transparent local canvas
            draw = ImageDraw.Draw(local_canvas)
            
            # Coordinates for drawing on the local_canvas (top-left is 0,0)
            coords = [0, 0, target_width, target_height]
            
            # Use the RGBA tuple for Pillow drawing functions
            fill_for_pillow = parsed_fill_color_tuple 
            stroke_for_pillow = None
            if stroke_width > 0:
                stroke_for_pillow = parsed_stroke_color_tuple if parsed_stroke_color_tuple else (0,0,0,255) # Default black if invalid

            if sub_type == 'rect':
                corner_radius = figure_data.get('cornerRadius', 0)
                # Adjust corner radius if it's larger than half the smallest dimension
                corner_radius = min(corner_radius, target_width / 2, target_height / 2)
                if corner_radius > 0:
                    draw.rounded_rectangle(coords, radius=corner_radius, fill=fill_for_pillow, outline=stroke_for_pillow, width=stroke_width)
                else:
                    draw.rectangle(coords, fill=fill_for_pillow, outline=stroke_for_pillow, width=stroke_width)
            elif sub_type == 'ellipse' or sub_type == 'circle':
                draw.ellipse(coords, fill=fill_for_pillow, outline=stroke_for_pillow, width=stroke_width)
            else:
                logger.warning(f"Unsupported figure subType '{sub_type}' for direct drawing (ID: {element_id}). Returning None.")
                return None
            scaled_figure = local_canvas

        # Create final canvas with element dimensions
        final_canvas = Image.new('RGBA', (final_width, final_height), (0,0,0,0))
        
        # Calculate crop starting point
        crop_start_x = int(round(crop_x * target_width))
        crop_start_y = int(round(crop_y * target_height))
        
        # Paste the scaled figure onto the final canvas with the appropriate offset
        paste_x = -crop_start_x
        paste_y = -crop_start_y
        
        logger.debug(f"Figure ID {element_id}: Pasting figure at offset ({paste_x}, {paste_y}) on final canvas")
        final_canvas.paste(scaled_figure, (paste_x, paste_y), scaled_figure if scaled_figure.mode == 'RGBA' else None)
        
        return final_canvas

    except ValueError as ve:
        logger.error(f"Data validation error for figure ID {element_id}: {ve}")
        return None # Or re-raise if processor.py should catch it explicitly as critical
    except Exception as e:
        logger.error(f"Error processing figure ID {element_id} for layer rendering: {e}", exc_info=True)
        return None


def process_figure(figure_data: Dict[str, Any], image: Image.Image) -> bool:
    """DEPRECATED: Process and draw figure elements directly onto a shared canvas. Returns True on success, False on handled failure."""
    logger.warning("Deprecated process_figure called. Consider switching to render_figure_to_image.")
    # This function is now a simple wrapper or could be removed.
    # For now, it won't do anything functional to avoid drawing on a shared canvas by mistake.
    element_id = figure_data.get('id', 'N/A')
    # To make it somewhat compatible for old calls, one might try to call the new function and paste, 
    # but that defeats the purpose of the refactor. Better to update callers.
    # rendered_layer = render_figure_to_image(figure_data)
    # if rendered_layer:
    #     x = int(figure_data.get('x',0))
    #     y = int(figure_data.get('y',0))
    #     image.paste(rendered_layer, (x,y), rendered_layer)
    #     return True
    logger.error(f"Deprecated process_figure for ID {element_id} was called but does not perform drawing operations anymore.")
    return False # Indicate it did not operate as old version did 