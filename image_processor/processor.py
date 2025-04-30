"""
Main image processor module.
Coordinates the overall image generation process.
"""

from PIL import Image, ImageDraw
from typing import Dict, Any

from .text_renderer import TextRenderer
from .figure_renderer import process_figure
from .image_handler import process_image
from .config import CONFIG
from .logger import get_logger
from utils.helpers import parse_color

logger = get_logger(__name__)

class ImageProcessor:
    """Main class for processing and combining images based on JSON templates."""

    @staticmethod
    def combine_images(json_data: Dict[str, Any]) -> Image.Image:
        """Combine all elements from JSON data into a single image, rendering in JSON array order."""
        try:
            # Validate input
            if not isinstance(json_data, dict) or 'pages' not in json_data:
                raise ValueError("Invalid JSON structure: missing 'pages' field")
                
            # Create a blank canvas
            canvas_width = int(json_data.get('width', CONFIG['canvas']['default_width']))
            canvas_height = int(json_data.get('height', CONFIG['canvas']['default_height']))
            bg_color = json_data.get('background', CONFIG['canvas']['default_bg_color'])
            
            logger.info(f"Creating canvas with dimensions {canvas_width}x{canvas_height}")
            canvas = Image.new('RGBA', (canvas_width, canvas_height), bg_color)
            draw = ImageDraw.Draw(canvas)
            
            # Process each page in order
            for page_idx, page in enumerate(json_data.get('pages', [])):
                logger.debug(f"Processing page {page_idx+1}/{len(json_data.get('pages', []))}")

                # --- Handle page-specific background color --- 
                page_bg_color_str = page.get('background')
                if page_bg_color_str:
                    # Try parsing the color string
                    page_bg_color_tuple = parse_color(page_bg_color_str, default_color=None)
                    if page_bg_color_tuple:
                        logger.info(f"Applying page {page_idx+1} background color: {page_bg_color_tuple}")
                        # Draw a rectangle covering the whole canvas with the page bg color
                        # This effectively sets the background for the elements on this page
                        draw.rectangle([0, 0, canvas_width, canvas_height], fill=page_bg_color_tuple)
                    else:
                        logger.warning(f"Could not parse page {page_idx+1} background color: '{page_bg_color_str}'. Using initial canvas background.")
                # -------------------------------------------

                if 'children' not in page:
                    logger.warning(f"Page {page_idx+1} has no children, skipping")
                    continue
                    
                # Iterate through children in order
                for child_idx, child in enumerate(page.get('children', [])):
                    element_type = child.get('type')
                    element_id = child.get('id', 'N/A')
                    
                    try:
                        if not child.get('visible', True):
                            logger.debug(f"Element {element_id} is not visible, skipping")
                            continue
                             
                        logger.debug(f"Processing element {element_id} of type {element_type}")
                        if element_type == 'figure':
                            process_figure(child, draw)
                        elif element_type == 'image':
                            # Process image normally
                            img, position = process_image(child) 
                            canvas.paste(img, position, img) 
                        elif element_type == 'text':
                            # Call TextRenderer directly
                            TextRenderer.render_text(canvas, child)
                        else:
                            logger.warning(f"Unknown element type '{element_type}' for ID: {element_id}")
                            
                    except Exception as e:
                        logger.error(f"Error processing element (ID: {element_id}, Type: {element_type}): {str(e)}")
                        # Continue processing other elements
            
            logger.info("Image creation complete")
            return canvas
            
        except Exception as e:
            logger.error(f"Error combining images: {str(e)}")
            raise 