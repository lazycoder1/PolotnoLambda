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
        color = text_data.get('fill', '#000000')
        parsed_color_tuple = None
        if isinstance(color, str):
            parsed_color_tuple = parse_color(color)
        else:
            parsed_color_tuple = color

        logger.debug(f"Text ID {text_data.get('id')}: Parsed fill color '{color}' -> {parsed_color_tuple}")

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
                line_x = x
                
                if alignment == 'center':
                    line_x = x + (max_width - line_width) / 2
                elif alignment == 'right':
                    line_x = x + max_width - line_width
                
                if text_contains_devanagari:
                    points = ' '.join([f'U+{ord(c):04X}' for c in line])
                    logger.debug(f"Drawing Devanagari line: {points}")
                
                logger.debug(
                    f"DrawWrap ID: {text_data.get('id')} | Align: {alignment} | "
                    f"OrigX: {x:.2f} | ElemW: {max_width:.2f} | LineW: {line_width:.2f} | "
                    f"DrawX: {line_x:.2f}"
                )
                draw.text((line_x, current_y), line, font=pil_font, fill=parsed_color_tuple)
                current_y += line_height
        else:
            text_width = pil_font.getlength(text)
            draw_x = x

            element_width = text_data.get('width')
            if alignment == 'center':
                if element_width:
                    draw_x = x + (element_width - text_width) / 2
                else:
                    logger.warning(f"Center alignment requested for single line text ID {text_data.get('id')}, but element 'width' is not defined. Using original x.")
            elif alignment == 'right':
                if element_width:
                     draw_x = x + element_width - text_width
                else:
                    logger.warning(f"Right alignment requested for single line text ID {text_data.get('id')}, but element 'width' is not defined. Reverting to left alignment.")
            
            logger.debug(
                f"DrawSingle ID: {text_data.get('id')} | Align: {alignment} | "
                f"OrigX: {x:.2f} | ElemW: {element_width or 'N/A'} | TextW: {text_width:.2f} | "
                f"DrawX: {draw_x:.2f}"
            )
            draw.text((draw_x, y), text, font=pil_font, fill=parsed_color_tuple)