"""
Text renderer module.
Handles text processing, wrapping, and rendering with various styles.
"""

from PIL import ImageFont, ImageDraw
from utils.helpers import parse_color, contains_devanagari
import unicodedata
from image_processor.logger import get_logger

logger = get_logger(__name__)

class TextRenderer:
    """Handles the rendering of text onto images."""
    
    @staticmethod
    def normalize_unicode(text: str) -> str:
        """Normalize Unicode to ensure consistent rendering of Devanagari text."""
        return unicodedata.normalize('NFC', text)
    
    @staticmethod
    def render_text(image, text_data, font_mgr):
        """Render text onto the image according to the provided text_data."""
        draw = ImageDraw.Draw(image)
        text = text_data.get('text', '')
        
        if not text:
            return
        
        text = TextRenderer.normalize_unicode(text)
        font_size = text_data.get('fontSize', 20)
        
        font_family = text_data.get('fontFamily', 'Arial')
        font_variant = text_data.get('fontVariant', 'Regular')
        
        # Use get_font directly instead of get_font_path followed by truetype - FontManager handles this logic
        pil_font = font_mgr.get_font(font_family, font_variant, font_size)
        
        # If we still have no font, use Pillow's default as last resort
        if not pil_font:
            logger.error(f"All font loading strategies failed for {font_family} {font_variant} (Text ID: {text_data.get('id', '')}). Using Pillow default.")
            try:
                pil_font = ImageFont.load_default()
            except Exception as e:
                logger.critical(f"Failed to load even Pillow's default font! Text may not render: {e}")
                return  # Cannot render without a font
        
        x = text_data.get('x', 0)
        y = text_data.get('y', 0)
        
        text_contains_devanagari = contains_devanagari(text)
        fill_color_str = text_data.get('fill', '#000000')
        parsed_fill_color = parse_color(fill_color_str) if isinstance(fill_color_str, str) else fill_color_str

        logger.debug(f"Text ID {text_data.get('id')}: Parsed text fill color '{fill_color_str}' -> {parsed_fill_color}")

        # Initialize background properties with defaults
        parsed_bg_color = None
        actual_padding = 0
        actual_corner_radius = 0

        if text_data.get('backgroundEnabled', False):
            bg_color_str = text_data.get('backgroundColor', 'rgba(0,0,0,0)') # Default to fully transparent
            parsed_bg_color = parse_color(bg_color_str) if isinstance(bg_color_str, str) else bg_color_str
            
            padding_factor = text_data.get('backgroundPadding', 0.0)
            corner_radius_factor = text_data.get('backgroundCornerRadius', 0.0)

            # Calculate actual pixel values from factors and font_size
            actual_padding = padding_factor * font_size 
            actual_corner_radius = corner_radius_factor * font_size
            
            # Ensure corner radius is not excessively large, e.g., cap it relative to padding or a fraction of font_size
            # For example, cap radius at actual_padding or font_size to avoid strange shapes.
            # This is a simple heuristic; more sophisticated logic might be needed for perfect visuals.
            if actual_corner_radius > 0:
                 actual_corner_radius = min(actual_corner_radius, actual_padding + font_size / 2)


            logger.info(f"Text ID {text_data.get('id')}: Background enabled. Color: {bg_color_str}->{parsed_bg_color}, PaddingFactor: {padding_factor}, CornerRadiusFactor: {corner_radius_factor}")
            logger.info(f"Text ID {text_data.get('id')}: FontSize: {font_size}px -> ActualPadding: {actual_padding:.2f}px, ActualCornerRadius: {actual_corner_radius:.2f}px")
        
        alignment = text_data.get('align', 'left')
        max_width = text_data.get('width')
        
        if max_width:
            words = text.split()
            wrapped_lines = []
            current_line = ""
            
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                if not current_line or pil_font.getlength(test_line) <= max_width:
                    current_line = test_line
                else:
                    wrapped_lines.append(current_line)
                    current_line = word
            
            if current_line:
                wrapped_lines.append(current_line)
                
            try:
                bbox = pil_font.getbbox("Agy")
                line_height = (bbox[3] - bbox[1]) * text_data.get('lineHeight', 1.2)
            except (AttributeError, TypeError):
                line_height = font_size * 1.2
            
            current_y = y
            for line in wrapped_lines:
                line_width = pil_font.getlength(line)
                line_x = x # Default to original x for line_x_for_align calculation
                
                if alignment == 'center':
                    line_x = x + (max_width - line_width) / 2
                elif alignment == 'right':
                    line_x = x + max_width - line_width
                
                # Get the bounding box of the line of text itself using textbbox with anchor='lt'
                try:
                    # textbbox uses (x, y) as the anchor point (top-left with "lt")
                    text_line_bbox = draw.textbbox((line_x, current_y), line, font=pil_font, anchor="lt")
                except AttributeError: # Fallback for older Pillow versions without 'anchor' in textbbox
                    logger.warning(f"Text ID {text_data.get('id')} (wrapped line): textbbox does not support 'anchor'. Background positioning might be less precise.")
                    line_height_approx = font_size # Approximate height
                    text_line_bbox = (line_x, current_y, line_x + line_width, current_y + line_height_approx)
                except Exception as e_bbox:
                    logger.error(f"Text ID {text_data.get('id')} (wrapped line): Error getting textbbox for line '{line}': {e_bbox}. Background may be incorrect.")
                    line_height_approx = font_size
                    text_line_bbox = (line_x, current_y, line_x + line_width, current_y + line_height_approx)

                if text_data.get('backgroundEnabled', False) and parsed_bg_color:
                    bg_coords = (
                        text_line_bbox[0] - actual_padding,
                        text_line_bbox[1] - actual_padding,
                        text_line_bbox[2] + actual_padding,
                        text_line_bbox[3] + actual_padding
                    )
                    logger.debug(f"Text ID {text_data.get('id')} Line BG: Drawing for '{line}' at {bg_coords} R:{actual_corner_radius}")
                    draw.rounded_rectangle(bg_coords, radius=actual_corner_radius, fill=parsed_bg_color)

                if text_contains_devanagari:
                    points = ' '.join([f'U+{ord(c):04X}' for c in line])
                    logger.debug(f"Drawing Devanagari line: {points}")
                
                logger.debug(
                    f"DrawWrap ID: {text_data.get('id')} | Align: {alignment} | "
                    f"OrigX: {x:.2f} | ElemW: {max_width:.2f} | LineW: {line_width:.2f} | "
                    f"DrawX: {line_x:.2f}"
                )
                draw.text((line_x, current_y), line, font=pil_font, fill=parsed_fill_color)
                current_y += line_height
        else:
            text_width = pil_font.getlength(text)
            draw_x = x

            element_width_single = text_data.get('width') 
            if alignment == 'center':
                if element_width_single:
                    draw_x = x + (element_width_single - text_width) / 2
                else: # If no element width, center alignment is meaningless for a single line relative to its own bounds
                    logger.warning(f"Center alignment for single line text ID {text_data.get('id')} without 'width' property; position based on x only.")
            elif alignment == 'right':
                if element_width_single:
                     draw_x = x + element_width_single - text_width
                else: # If no element width, right alignment is meaningless
                    logger.warning(f"Right alignment requested for single line text ID {text_data.get('id')}, but element 'width' is not defined. Reverting to left alignment behavior.")
            
            # Get bounding box for single line text
            try:
                text_line_bbox_single = draw.textbbox((draw_x, y), text, font=pil_font, anchor="lt")
            except AttributeError: # Fallback for older Pillow
                logger.warning(f"Text ID {text_data.get('id')} (single line): textbbox does not support 'anchor'. Background positioning might be less precise.")
                text_height_approx_single = font_size
                text_line_bbox_single = (draw_x, y, draw_x + text_width, y + text_height_approx_single)
            except Exception as e_bbox_single:
                logger.error(f"Text ID {text_data.get('id')} (single line): Error getting textbbox for '{text}': {e_bbox_single}. Background may be incorrect.")
                text_height_approx_single = font_size
                text_line_bbox_single = (draw_x, y, draw_x + text_width, y + text_height_approx_single)
            
            if text_data.get('backgroundEnabled', False) and parsed_bg_color:
                bg_coords_single = (
                    text_line_bbox_single[0] - actual_padding,
                    text_line_bbox_single[1] - actual_padding,
                    text_line_bbox_single[2] + actual_padding,
                    text_line_bbox_single[3] + actual_padding
                )
                logger.debug(f"Text ID {text_data.get('id')} SingleLineBG: Drawing for '{text}' at {bg_coords_single} R:{actual_corner_radius}")
                draw.rounded_rectangle(bg_coords_single, radius=actual_corner_radius, fill=parsed_bg_color)

            logger.debug(
                f"DrawSingle ID: {text_data.get('id')} | Align: {alignment} | "
                f"OrigX: {x:.2f} | ElemW: {element_width_single or 'N/A'} | TextW: {text_width:.2f} | "
                f"DrawX: {draw_x:.2f}"
            )
            draw.text((draw_x, y), text, font=pil_font, fill=parsed_fill_color)