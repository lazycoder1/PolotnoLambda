"""
Image handler module.
Handles loading, processing, and transforming images.
"""

from PIL import Image, ImageFilter, ImageEnhance
import requests
from io import BytesIO
from typing import Dict, Any, Tuple, Optional
import os # Keep os import if used elsewhere, or remove if only for the mistaken local path logic

from .image_effects import apply_image_effects, create_rounded_corners, rotate_image
from .config import CONFIG
from .logger import get_logger

logger = get_logger(__name__)

def load_image_from_url(url: str) -> Optional[Image.Image]:
    """Load image from URL and return PIL Image object, or None if URL is invalid/empty."""
    if not url or not isinstance(url, str) or not (url.startswith('http://') or url.startswith('https://')):
        logger.warning(f"Invalid or empty image URL provided: '{url}'. Skipping load.")
        return None
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for bad responses
        img = Image.open(BytesIO(response.content))
        # Ensure the image has an alpha channel if it's not already in RGBA mode
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        return img
    except requests.RequestException as e:
        logger.error(f"Failed to load image from URL '{url}': {e}")
        raise # Re-raise to be handled by the caller
    except Exception as e:
        logger.error(f"Error processing image from URL '{url}': {e}")
        raise # Re-raise to be handled by the caller

# Helper function to apply filters (like grayscale, sepia)
def apply_filters_pil(image: Image.Image, filters_data: list) -> Image.Image:
    # Assuming this function exists or is defined elsewhere, or its logic is inlined.
    # For this edit, we'll assume it's available.
    # Based on current code, it processes 'grayscale' and 'sepia'.
    # This should be applied to the image *before* scaling for the new crop logic.
    if not filters_data:
        return image
    
    img_copy = image.copy()
    for filter_item in filters_data:
        if not isinstance(filter_item, dict): continue
        filter_type = filter_item.get('type')
        if filter_type == 'grayscale':
            img_copy = img_copy.convert('L').convert('RGBA') # Preserve alpha
        elif filter_type == 'sepia':
            # Simple sepia, could be more sophisticated
            r, g, b, a = img_copy.split()
            r = r.point(lambda i: i * 0.393 + i * 0.769 + i * 0.189)
            g = g.point(lambda i: i * 0.349 + i * 0.686 + i * 0.168)
            b = b.point(lambda i: i * 0.272 + i * 0.534 + i * 0.131)
            img_copy = Image.merge('RGBA', (r, g, b, a))
    return img_copy

# Helper function to apply effects (like blur, brightness)
def apply_effects_pil(image: Image.Image, image_data: dict) -> Image.Image:
    # This processes 'blur', 'imageBrightness', 'contrast', 'saturate', 'hueRotate'.
    # This should be applied to the final composited element canvas.
    img_copy = image.copy() # Work on a copy

    # Blur
    blur_radius = image_data.get('blur', 0)
    if blur_radius > 0:
        img_copy = img_copy.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Brightness, Contrast, Saturation, Hue (using ImageEnhance)
    enhancer_applied = False
    brightness = image_data.get('imageBrightness', 1.0) # Default 1.0 (no change)
    if brightness != 1.0:
        enhancer = ImageEnhance.Brightness(img_copy)
        img_copy = enhancer.enhance(brightness)
        enhancer_applied = True
    
    contrast = image_data.get('contrast', 1.0) # Default 1.0 (no change)
    if contrast != 1.0:
        enhancer = ImageEnhance.Contrast(img_copy)
        img_copy = enhancer.enhance(contrast)
        enhancer_applied = True

    saturation = image_data.get('saturate', 1.0) # Default 1.0 (no change)
    # Pillow's Color enhancer is for saturation.
    if saturation != 1.0:
        enhancer = ImageEnhance.Color(img_copy)
        img_copy = enhancer.enhance(saturation)
        enhancer_applied = True
        
    # Hue rotation is complex with Pillow. Skip for now unless a clear method is available.
    # hue_rotate_deg = image_data.get('hueRotate', 0)
    # if hue_rotate_deg != 0:
    # logger.warning("Hue rotation is not directly supported by Pillow ImageEnhance in this simplified version.")
            
    return img_copy

def process_image(image_data: Dict[str, Any]) -> tuple[Image.Image | None, tuple[int, int]]:
    """
    Processes an image element: loads, filters, scales, crops, and applies effects.
    Implements the proper scaling and cropping logic as documented:
    1. Determine constrained dimension
    2. Calculate target dimensions
    3. Scale image proportionally
    4. Apply cropping
    """
    try:
        src = image_data.get('src')
        if not src:
            logger.error("Image source ('src') is missing in image_data.")
            return None, (0, 0)
            
        img = load_image_from_url(src)
        if not img:
            logger.error(f"Failed to load image from src: {src}")
            return None, (image_data.get('x',0), image_data.get('y',0))

        orig_width, orig_height = img.size
        
        # Get the desired final dimensions
        final_width = int(round(image_data.get('width', orig_width)))
        final_height = int(round(image_data.get('height', orig_height)))

        # 1. Apply Filters (e.g., grayscale, sepia) to the original loaded image
        filters_data = image_data.get('filters')
        if filters_data and isinstance(filters_data, list):
            logger.debug(f"Applying filters {filters_data} to image ID {image_data.get('id')}")
            img = apply_filters_pil(img, filters_data)
            
        # 2. Get crop parameters
        crop_x = image_data.get('cropX', 0.0)
        crop_y = image_data.get('cropY', 0.0)
        crop_width = image_data.get('cropWidth', 1.0)
        crop_height = image_data.get('cropHeight', 1.0)
        
        # 3. Calculate the target dimensions based on our documented approach
        target_width = 0
        target_height = 0
        scale_factor = 1.0
        
        # Determine which dimension is constrained
        if crop_width < 1.0 and crop_height == 1.0:
            # Width-constrained calculation
            target_width = int(round(final_width / crop_width))
            scale_factor = target_width / orig_width
            target_height = int(round(orig_height * scale_factor))
            logger.info(f"Width-constrained crop: Target dimensions {target_width}x{target_height}, scale factor {scale_factor}")
        elif crop_height < 1.0 and crop_width == 1.0:
            # Height-constrained calculation
            target_height = int(round(final_height / crop_height))
            scale_factor = target_height / orig_height
            target_width = int(round(orig_width * scale_factor))
            logger.info(f"Height-constrained crop: Target dimensions {target_width}x{target_height}, scale factor {scale_factor}")
        elif crop_width < 1.0 and crop_height < 1.0:
            # Both dimensions constrained - determine which one to prioritize
            # Calculate both scale factors and use the larger one to ensure both constraints are met
            width_scale = (final_width / crop_width) / orig_width
            height_scale = (final_height / crop_height) / orig_height
            
            if width_scale >= height_scale:
                # Width constraint is more restrictive
                target_width = int(round(final_width / crop_width))
                scale_factor = target_width / orig_width
                target_height = int(round(orig_height * scale_factor))
                logger.info(f"Both constrained (width priority): {target_width}x{target_height}, scale factor {scale_factor}")
            else:
                # Height constraint is more restrictive
                target_height = int(round(final_height / crop_height))
                scale_factor = target_height / orig_height
                target_width = int(round(orig_width * scale_factor))
                logger.info(f"Both constrained (height priority): {target_width}x{target_height}, scale factor {scale_factor}")
        else:
            # Neither dimension is constrained, just scale to final size
            target_width = final_width
            target_height = final_height
            logger.info(f"No crop constraints: Target dimensions {target_width}x{target_height}")
        
        # 4. Scale the image
        scaled_image = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # 5. Create a transparent canvas of the final dimensions
        final_canvas = Image.new('RGBA', (final_width, final_height), (0, 0, 0, 0))
        
        # 6. Calculate the crop region
        crop_start_x = int(round(crop_x * target_width))
        crop_start_y = int(round(crop_y * target_height))
        
        # 7. Paste the cropped region onto the final canvas
        paste_x = -crop_start_x
        paste_y = -crop_start_y
        
        logger.debug(f"Image ID {image_data.get('id')}: Pasting scaled image at offset ({paste_x}, {paste_y}) on canvas")
        final_canvas.paste(scaled_image, (paste_x, paste_y), scaled_image if scaled_image.mode == 'RGBA' else None)
        
        # 8. Apply effects to the final composited canvas
        final_img_with_effects = apply_effects_pil(final_canvas, image_data)
        
        logger.info(f"Finished processing image ID {image_data.get('id')}. Final size: {final_img_with_effects.size}")
        return final_img_with_effects, (image_data.get('x', 0), image_data.get('y', 0))

    except Exception as e:
        logger.error(f"Error processing image_data for src {image_data.get('src', 'N/A')}: {e}", exc_info=True)
        return None, (image_data.get('x', 0), image_data.get('y', 0))

# Ensure ImageFilter and ImageEnhance are imported if not already:
# from PIL import ImageFilter, ImageEnhance 