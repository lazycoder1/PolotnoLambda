"""
Main image processor module.
Coordinates the overall image generation process.
"""
import os
from PIL import Image, ImageDraw, features
from typing import Dict, Any

import logging

from .text_renderer import TextRenderer
from .figure_renderer import process_figure, render_figure_to_image
from .image_handler import process_image
from .config import CONFIG
from .logger import get_logger
from utils.helpers import parse_color
from .font_manager import FontManager

logger = get_logger(__name__)

class ImageProcessor:
    """Main class for processing and combining images based on JSON templates."""

    def __init__(self):
        """Initialize the ImageProcessor, checking dependencies and setting up FontManager."""
        
        try:
            import cairosvg
            logger.info("CairoSVG library imported successfully.")
        except ImportError as e:
            error_msg = (
                "Failed to import cairosvg. SVG rendering will not work. "
                "Ensure Cairo library and cairosvg Python package are installed correctly "
                "in the Lambda environment (e.g., via Dockerfile or Lambda layer). Error: {}"
            ).format(e)
            logger.error(error_msg)
            raise ImportError(error_msg)
        
        if not features.check('raqm'):
            logger.warning(
                "Pillow RAQM feature check failed. Complex text layout (e.g., for Devanagari, Arabic) "
                "might not render correctly. Ensure libraqm library and its dependencies (FriBiDi, HarfBuzz) "
                "are installed and Pillow is compiled with Raqm support in the Lambda environment."
            )
        else:
            logger.info("Pillow RAQM feature detected. Complex text layout should be supported.")

        # Get environment variables and config
        google_api_key = os.environ.get("GOOGLE_API_KEY")
        font_s3_bucket_name = os.environ.get("FONT_S3_BUCKET", "upwork-fonts-assets")
        
        # Set up the default font path
        default_font_relative_path = "fonts/Roboto-Regular.ttf"
        default_font_absolute_path = os.path.join(os.getcwd(), default_font_relative_path)

        # Check if default font exists
        if not os.path.exists(default_font_absolute_path):
            logger.warning(
                f"Default font file not found at {default_font_absolute_path}. "
                f"Ensure it is bundled with the Lambda in the /fonts/ directory "
                f"at the root of the deployment package. FontManager may need to rely on S3 or Google Fonts."
            )

        # Initialize FontManager with the default font path
        self.font_mgr = FontManager(
            s3_bucket_name=font_s3_bucket_name,
            google_api_key=google_api_key,
            default_font_path=default_font_absolute_path
        )
        
        logger.info("ImageProcessor initialized with FontManager.")
        
        if not google_api_key:
            logger.warning(
                "GOOGLE_API_KEY environment variable not set during ImageProcessor initialization. "
                "FontManager will rely on S3 cache or default font only. "
                "Fetching new fonts from Google Fonts will fail."
            )

    def combine_images(self, json_data: Dict[str, Any]) -> tuple[Image.Image, list]:
        """Combine all elements from JSON data into a single image, returning the image and any element processing errors."""
        element_processing_errors = [] 
        try:
            if not isinstance(json_data, dict) or 'pages' not in json_data:
                element_processing_errors.append("Invalid JSON structure: missing 'pages' field")
                raise ValueError("Invalid JSON structure: missing 'pages' field")
                
            final_canvas_width = int(json_data.get('width', CONFIG['canvas']['default_width']))
            final_canvas_height = int(json_data.get('height', CONFIG['canvas']['default_height']))
            
            # --- Stage 1: Prepare all element layers --- 
            prepared_layers = []
            for page_idx, page in enumerate(json_data.get('pages', [])):
                logger.debug(f"Preparing elements for page {page_idx+1}")
                if 'children' not in page:
                    logger.warning(f"Page {page_idx+1} has no children, skipping")
                    continue

                for child_idx, child_data in enumerate(page.get('children', [])):
                    element_type = child_data.get('type')
                    element_id = child_data.get('id', 'N/A')
                    error_prefix = f"Element (ID: {element_id}, Type: {element_type}, Index: {child_idx} on Page: {page_idx+1})"
                    
                    try:
                        if not child_data.get('visible', True):
                            logger.debug(f"Element {element_id} is not visible, skipping preparation")
                            continue
                        
                        element_image: Image.Image | None = None # Ensure type hint
                        element_x = int(child_data.get('x', 0))
                        element_y = int(child_data.get('y', 0))
                        
                        if element_type == 'figure':
                            element_image = render_figure_to_image(child_data)
                            if not element_image:
                                raise ValueError("Figure element could not be processed into an image layer.")

                        elif element_type == 'image':
                            processed_image_data = process_image(child_data)
                            if processed_image_data:
                                element_image, coords = processed_image_data
                                element_x, element_y = coords  # Unpack correctly from the tuple
                            else:
                                raise ValueError(f"Image could not be processed or loaded. Src: {child_data.get('src', 'N/A')}")
                        
                        elif element_type == 'text':
                            element_image = TextRenderer.render_text_to_image(child_data, self.font_mgr)
                            if not element_image:
                                raise ValueError("Text element could not be rendered to an image layer.")
                        else:
                            # Corrected error message formatting
                            raise ValueError(f"Unknown element type '{element_type}'") 

                        if element_image:
                            prepared_layers.append({
                                'image': element_image,
                                'x': element_x,
                                'y': element_y,
                                'data': child_data 
                            })
                            
                    except Exception as e:
                        err_msg = f"{error_prefix}: Failed during layer preparation: {str(e)}"
                        logger.error(err_msg, exc_info=True)
                        element_processing_errors.append(err_msg)
            
            if not prepared_layers:
                logger.warning("No visible elements were prepared. Returning blank canvas based on final dimensions.")
                page_data_for_bg = json_data.get('pages', [{}])[0]
                bg_color_str = page_data_for_bg.get('background', json_data.get('background', CONFIG['canvas']['default_bg_color']))
                bg_color = parse_color(bg_color_str, default_color=(255,255,255,0))
                blank_canvas = Image.new('RGBA', (final_canvas_width, final_canvas_height), bg_color)
                return blank_canvas, element_processing_errors

            # --- Stage 2: Calculate "Giant Canvas" dimensions --- 
            min_overall_x, min_overall_y = float('inf'), float('inf')
            max_overall_x_extent, max_overall_y_extent = float('-inf'), float('-inf')

            for layer in prepared_layers:
                img = layer['image']
                x, y = layer['x'], layer['y']
                min_overall_x = min(min_overall_x, x)
                min_overall_y = min(min_overall_y, y)
                max_overall_x_extent = max(max_overall_x_extent, x + img.width)
                max_overall_y_extent = max(max_overall_y_extent, y + img.height)
            
            giant_canvas_width = int(max_overall_x_extent - min_overall_x)
            giant_canvas_height = int(max_overall_y_extent - min_overall_y)
            giant_canvas_width = max(1, giant_canvas_width) 
            giant_canvas_height = max(1, giant_canvas_height)

            logger.info(f"Giant canvas dimensions: {giant_canvas_width}x{giant_canvas_height}. Min X/Y: ({min_overall_x},{min_overall_y})")
            giant_canvas = Image.new('RGBA', (giant_canvas_width, giant_canvas_height), (0, 0, 0, 0)) 

            # --- Stage 3: Paste layers onto "Giant Canvas" --- 
            for layer in prepared_layers:
                element_img = layer['image']
                paste_x = int(layer['x'] - min_overall_x)
                paste_y = int(layer['y'] - min_overall_y)
                element_data = layer['data']
                
                opacity = element_data.get('opacity', 1.0)
                if opacity < 1.0 and element_img.mode == 'RGBA':
                    alpha = element_img.split()[3]
                    alpha = alpha.point(lambda p: int(p * opacity)) # Ensure int for Pillow
                    element_img.putalpha(alpha)
                
                logger.debug(f"Pasting element {element_data.get('id')} at ({paste_x},{paste_y}) on giant canvas. Size: {element_img.size}")
                giant_canvas.paste(element_img, (paste_x, paste_y), element_img if element_img.mode == 'RGBA' else None)

            # --- Stage 4: Create Final Output Canvas and crop from Giant Canvas --- 
            page_data = json_data.get('pages', [{}])[0] 
            bg_color_str = page_data.get('background', json_data.get('background', CONFIG['canvas']['default_bg_color']))
            bg_color = parse_color(bg_color_str, default_color=(255,255,255,255))
            
            # Create output canvas with the exact same dimensions as specified in the json_data
            output_canvas = Image.new('RGBA', (final_canvas_width, final_canvas_height), bg_color)
            
            crop_source_x = int(0 - min_overall_x)
            crop_source_y = int(0 - min_overall_y)
            
            crop_box = (
                crop_source_x,
                crop_source_y,
                crop_source_x + final_canvas_width,
                crop_source_y + final_canvas_height
            )
            logger.info(f"Cropping from giant canvas using box: {crop_box}")
            
            actual_crop_box = (
                max(0, crop_box[0]),
                max(0, crop_box[1]),
                min(giant_canvas_width, crop_box[2]),
                min(giant_canvas_height, crop_box[3])
            )
            
            if actual_crop_box[2] > actual_crop_box[0] and actual_crop_box[3] > actual_crop_box[1]:
                # Crop the region from the giant canvas
                cropped_region = giant_canvas.crop(actual_crop_box)
                
                # Calculate where to paste on the output canvas
                paste_on_output_x = 0
                paste_on_output_y = 0
                if crop_box[0] < 0:
                    paste_on_output_x = -crop_box[0]
                if crop_box[1] < 0:
                    paste_on_output_y = -crop_box[1]
                
                # Create a new output canvas that is exactly the size of the cropped region 
                # to ensure we don't resize the final image
                if cropped_region.width != final_canvas_width or cropped_region.height != final_canvas_height:
                    # Only use the original canvas if we need to position the cropped region
                    # at a specific offset or if there's a background color
                    if paste_on_output_x > 0 or paste_on_output_y > 0 or any(c > 0 for c in bg_color):
                        # Paste the cropped region at the calculated position
                        output_canvas.paste(cropped_region, (paste_on_output_x, paste_on_output_y), 
                                           cropped_region if cropped_region.mode == 'RGBA' else None)
                    else:
                        # Just use the cropped region directly as our output - no resizing
                        output_canvas = cropped_region
                else:
                    # The cropped region matches the target size exactly - paste it
                    output_canvas.paste(cropped_region, (paste_on_output_x, paste_on_output_y), 
                                       cropped_region if cropped_region.mode == 'RGBA' else None)
            else:
                logger.warning("Calculated crop box is invalid or outside giant canvas. Output might be blank or only background.")

            if element_processing_errors:
                logger.warning(f"Image generation completed with {len(element_processing_errors)} element-level errors/warnings.")
            else:
                logger.info("Image creation process complete with giant canvas logic.")
            return output_canvas, element_processing_errors
            
        except Exception as e:
            logger.error(f"Critical error in combine_images: {str(e)}", exc_info=True)
            element_processing_errors.append(f"Critical error in combine_images: {str(e)}")
            # Fallback to a blank/error image of final size
            final_fallback_image = Image.new('RGBA', 
                                     (json_data.get('width', CONFIG['canvas']['default_width']), 
                                      json_data.get('height', CONFIG['canvas']['default_height'])), 
                                     (255, 0, 0, 255)) # Red canvas
            return final_fallback_image, element_processing_errors 