"""
Text renderer module.
Handles text processing, wrapping, and rendering with various styles.
"""

from PIL import ImageFont, ImageDraw
from .font_manager import FontManager
from utils.helpers import parse_color, contains_devanagari
import unicodedata
from image_processor.logger import get_logger

logger = get_logger(__name__)

class TextRenderer:
    """Handles the rendering of text onto images."""
    
    @staticmethod
    def normalize_unicode(text: str) -> str:
        """Normalize Unicode to ensure consistent rendering of Devanagari text."""
        # Change back to NFC normalization to match font_manager.py
        return unicodedata.normalize('NFC', text)
    
    @staticmethod
    def render_text(image, text_data):
        """Render text onto the image according to the provided text_data."""
        # Set up defaults
        draw = ImageDraw.Draw(image)
        text = text_data.get('text', '')
        
        # Early return if no text
        if not text:
            return
        
        # Apply Unicode normalization - use NFC for consistency with font_manager
        text = TextRenderer.normalize_unicode(text)
        
        # Get position and size
        font_size = text_data.get('fontSize', 20)
        
        # Select the appropriate font
        font, font_source = FontManager.select_font(text_data, font_size)
        if font is None:
            logger.warning(f"No suitable font found for text \"{text_data.get('text', '')[:20]}...\". Using default.")
            font = ImageFont.load_default()
        
        x = text_data.get('x', 0)
        y = text_data.get('y', 0)
        
        # Check if this contains Devanagari
        text_contains_devanagari = contains_devanagari(text)
        
        # Get color (either direct color or hex string)
        color = text_data.get('fill', '#000000')
        parsed_color_tuple = None # Initialize
        if isinstance(color, str):
            parsed_color_tuple = parse_color(color)
        else:
            parsed_color_tuple = color # Assume it's already a tuple if not a string

        # --- Add this line for debugging --- 
        logger.debug(f"Text ID {text_data.get('id')}: Parsed fill color '{color}' -> {parsed_color_tuple}")
        # -------------------------------------

        # Handle text alignment
        alignment = text_data.get('align', 'left')
        
        # Handle text wrapping if width is specified
        max_width = text_data.get('width')
        if max_width:
            # Calculate wrapped lines
            words = text.split()
            wrapped_lines = []
            current_line = ""
            
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                if not current_line or font.getlength(test_line) <= max_width:
                    current_line = test_line
                else:
                    wrapped_lines.append(current_line)
                    current_line = word
            
            if current_line:
                wrapped_lines.append(current_line)
                
            # Get line height
            try:
                bbox = font.getbbox("Agy")
                line_height = (bbox[3] - bbox[1]) * text_data.get('lineHeight', 1.2)
            except (AttributeError, TypeError):
                line_height = font_size * 1.2
            
            # Draw each line with proper alignment
            current_y = y
            for line in wrapped_lines:
                line_width = font.getlength(line)
                line_x = x
                
                if alignment == 'center':
                    line_x = x + (max_width - line_width) / 2
                elif alignment == 'right':
                    line_x = x + max_width - line_width
                
                # Special handling for Devanagari text
                if text_contains_devanagari:
                    # Print the Unicode points for debugging
                    points = ' '.join([f'U+{ord(c):04X}' for c in line])
                    logger.debug(f"Drawing Devanagari line: {points}")
                
                # Draw the text
                # --- Add this block for debugging ---
                logger.debug(
                    f"DrawWrap ID: {text_data.get('id')} | Align: {alignment} | "
                    f"OrigX: {x:.2f} | ElemW: {max_width:.2f} | LineW: {line_width:.2f} | "
                    f"DrawX: {line_x:.2f}"
                )
                # -------------------------------------
                draw.text((line_x, current_y), line, font=font, fill=parsed_color_tuple)
                current_y += line_height
        else:
            # Single line text
            # Calculate starting X based on alignment for single line text
            # Requires the element's width for center/right alignment
            element_width = text_data.get('width') # Get element width if available
            text_width = font.getlength(text)
            draw_x = x # Default to left alignment (original x)

            if alignment == 'center':
                if element_width:
                    draw_x = x + (element_width - text_width) / 2
                else:
                    # Fallback if width not specified: center based on text width relative to x?
                    # This might not be visually correct if x isn't the intended center point.
                    logger.warning(f"Center alignment requested for single line text ID {text_data.get('id')}, but element 'width' is not defined. Centering based on x.")
                    # The previous logic 'x = x - text_width / 2' was likely incorrect.
                    # We'll just use the original x for now.
                    draw_x = x # Revert to left align if width missing
            elif alignment == 'right':
                if element_width:
                     draw_x = x + element_width - text_width
                else:
                    logger.warning(f"Right alignment requested for single line text ID {text_data.get('id')}, but element 'width' is not defined. Reverting to left alignment.")
                    draw_x = x # Revert to left align if width missing
            
            # Draw the text
            # --- Add this block for debugging ---
            logger.debug(
                f"DrawSingle ID: {text_data.get('id')} | Align: {alignment} | "
                f"OrigX: {x:.2f} | ElemW: {element_width or 'N/A'} | TextW: {text_width:.2f} | "
                f"DrawX: {draw_x:.2f}"
            )
            # -------------------------------------
            draw.text((draw_x, y), text, font=font, fill=parsed_color_tuple)