"""
Main image processor module.
Coordinates the overall image generation process.
"""
import os
from PIL import Image, ImageDraw, features
from typing import Dict, Any

import logging

from .text_renderer import TextRenderer
from .figure_renderer import process_figure
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

    def combine_images(self, json_data: Dict[str, Any]) -> Image.Image:
        """Combine all elements from JSON data into a single image, returning the image and any element processing errors."""
        element_processing_errors = [] # To store errors for individual elements
        try:
            if not isinstance(json_data, dict) or 'pages' not in json_data:
                # This is a fundamental error, not an element error
                raise ValueError("Invalid JSON structure: missing 'pages' field")
                
            canvas_width = int(json_data.get('width', CONFIG['canvas']['default_width']))
            canvas_height = int(json_data.get('height', CONFIG['canvas']['default_height']))
            bg_color_str = json_data.get('background', CONFIG['canvas']['default_bg_color'])
            bg_color = parse_color(bg_color_str, default_color=(255,255,255,255)) # Provide a default tuple
            
            logger.info(f"Creating canvas with dimensions {canvas_width}x{canvas_height}")
            canvas = Image.new('RGBA', (canvas_width, canvas_height), bg_color)
            draw = ImageDraw.Draw(canvas)
            
            for page_idx, page in enumerate(json_data.get('pages', [])):
                logger.debug(f"Processing page {page_idx+1}/{len(json_data.get('pages', []))}")

                page_bg_color_str = page.get('background')
                if page_bg_color_str:
                    page_bg_color_tuple = parse_color(page_bg_color_str, default_color=None)
                    if page_bg_color_tuple:
                        logger.info(f"Applying page {page_idx+1} background color: {page_bg_color_tuple}")
                        draw.rectangle([0, 0, canvas_width, canvas_height], fill=page_bg_color_tuple)
                    else:
                        logger.warning(f"Could not parse page {page_idx+1} background color: '{page_bg_color_str}'. Using initial canvas background.")

                if 'children' not in page:
                    logger.warning(f"Page {page_idx+1} has no children, skipping")
                    continue # Or append to errors if this is considered an issue
                    
                for child_idx, child in enumerate(page.get('children', [])):
                    element_type = child.get('type')
                    element_id = child.get('id', 'N/A')
                    error_prefix = f"Element (ID: {element_id}, Type: {element_type}, Index: {child_idx} on Page: {page_idx+1})"
                    
                    try:
                        if not child.get('visible', True):
                            logger.debug(f"Element {element_id} is not visible, skipping")
                            continue
                             
                        logger.debug(f"Processing element {element_id} of type {element_type}")
                        if element_type == 'figure':
                            # Assuming process_figure might raise an exception on failure or we adapt it
                            process_figure(child, canvas) # If process_figure can fail and not raise, it needs to signal error
                        elif element_type == 'image':
                            processed_image_data = process_image(child) # process_image now returns None on failure
                            if processed_image_data:
                                img, position = processed_image_data
                                # img should be valid if processed_image_data is not None
                                canvas.paste(img, position, img) 
                            else:
                                err_msg = f"{error_prefix}: Image could not be processed or loaded. Src: {child.get('src', 'N/A')}"
                                logger.warning(err_msg)
                                element_processing_errors.append(err_msg)
                        elif element_type == 'text':
                            # Assuming TextRenderer.render_text might raise an exception on failure
                            TextRenderer.render_text(canvas, child, self.font_mgr)
                        else:
                            warn_msg = f"{error_prefix}: Unknown element type '{element_type}'"
                            logger.warning(warn_msg)
                            element_processing_errors.append(warn_msg) # Treat unknown type as an error/warning
                            
                    except Exception as e:
                        err_msg = f"{error_prefix}: Failed due to: {str(e)}"
                        logger.error(err_msg, exc_info=True) # Keep detailed log
                        element_processing_errors.append(err_msg) # Add concise error for summary
            
            logger.info("Image creation process complete.")
            if element_processing_errors:
                logger.warning(f"Image generation completed with {len(element_processing_errors)} element-level errors/warnings.")
            return canvas, element_processing_errors # Return both
            
        except Exception as e:
            # This catches errors in canvas setup or other fundamental issues
            logger.error(f"Critical error in combine_images: {str(e)}", exc_info=True)
            # Return None for canvas and the error message, or re-raise if this path shouldn't be handled by the caller similarly
            return None, [f"Critical error in combine_images: {str(e)}"] # Ensure consistent return type 