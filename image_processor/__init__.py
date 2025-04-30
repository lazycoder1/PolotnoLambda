# image_processor/__init__.py

"""
Image Processing module for marketing image generation.
Handles image manipulation, text rendering, and composition.
"""

# Import configuration and logging setup first
from .config import CONFIG
from .logger import get_logger

# Import processing components
from .processor import ImageProcessor
from .image_handler import process_image, load_image_from_url
from .image_effects import apply_image_effects, create_rounded_corners, rotate_image
from .text_renderer import TextRenderer
from .figure_renderer import process_figure
from .font_manager import FontManager

# Initialize the logger
logger = get_logger(__name__)
logger.info("Image processor module initialized")

# You could also expose other core functions if needed, e.g.:
# from .elements import process_image, process_text, process_figure
# from .fonts import get_font

__all__ = [
    'ImageProcessor',
    'process_image',
    'load_image_from_url',
    'apply_image_effects',
    'TextRenderer',
    'process_figure',
    'FontManager',
    'CONFIG',
    'get_logger'
] 