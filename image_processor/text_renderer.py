"""
Text renderer module.
Handles text processing, wrapping, and rendering with various styles.
"""

from PIL import ImageFont, ImageDraw, Image
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
    
    @staticmethod # New method to render text to its own image layer
    def render_text_to_image(text_data: dict, font_mgr) -> Image.Image:
        """Renders text onto a new transparent image sized to the element's dimensions."""
        element_id = text_data.get('id', 'N/A')
        element_width = int(text_data.get('width', 100)) # Default width if not specified
        element_height = int(text_data.get('height', 30)) # Default height if not specified

        # Ensure minimum dimensions
        element_width = max(1, element_width)
        element_height = max(1, element_height)

        local_canvas = Image.new('RGBA', (element_width, element_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(local_canvas)

        text = text_data.get('text', '')
        if not text:
            logger.debug(f"Text ID {element_id}: Empty text, returning blank local canvas.")
            return local_canvas
        
        text = TextRenderer.normalize_unicode(text)
        font_size = text_data.get('fontSize', 20)
        font_family = text_data.get('fontFamily', 'Arial')
        font_variant = text_data.get('fontVariant', 'Regular')

        pil_font = font_mgr.get_font(font_family, font_variant, font_size)
        if not pil_font:
            logger.error(f"Text ID {element_id}: Font {font_family} {font_variant} not loaded. Using Pillow default.")
            try:
                pil_font = ImageFont.load_default()
            except Exception as e:
                logger.critical(f"Text ID {element_id}: Failed to load Pillow default font: {e}. Returning blank canvas.")
                return local_canvas # Cannot render without font

        fill_color_str = text_data.get('fill', '#000000')
        parsed_fill_color = parse_color(fill_color_str)

        # Background properties
        parsed_bg_color = None
        actual_padding = 0
        actual_corner_radius = 0

        if text_data.get('backgroundEnabled', False):
            bg_color_str = text_data.get('backgroundColor', 'rgba(0,0,0,0)')
            parsed_bg_color = parse_color(bg_color_str)
            
            # Handle background opacity separately from the color's alpha
            bg_opacity = text_data.get('backgroundOpacity', 1.0)
            if parsed_bg_color and bg_opacity < 1.0:
                # If parsed_bg_color has alpha, adjust it by bg_opacity
                r, g, b, a = parsed_bg_color
                a = int(a * bg_opacity)
                parsed_bg_color = (r, g, b, a)
                logger.debug(f"Text ID {element_id}: Applied backgroundOpacity {bg_opacity} to background color, resulting alpha: {a}")
                
            # Get padding and corner radius as factors of font size
            padding_factor = text_data.get('backgroundPadding', 0.0)
            corner_radius_factor = text_data.get('backgroundCornerRadius', 0.0)
            
            # Calculate actual pixel values
            actual_padding = max(0, padding_factor * font_size)
            
            # Apply a smaller multiplier (0.6) to the corner radius to make it less prominent
            actual_corner_radius = max(0, corner_radius_factor * font_size * 0.6)
            
            if actual_corner_radius > 0:
                # Cap corner radius to prevent overly large/weird shapes relative to padding/font size
                # Use a more conservative cap that's a fraction of the padding to ensure smaller corners
                max_radius = min(
                    actual_padding * 0.8,  # 80% of the padding
                    font_size / 3,         # 1/3 of the font size (smaller than previous 1/2)
                    element_width / 4,     # 1/4 of element width (smaller than previous 1/2)
                    element_height / 4     # 1/4 of element height (smaller than previous 1/2)
                )
                actual_corner_radius = min(actual_corner_radius, max_radius)
                logger.debug(f"Text ID {element_id}: Corner radius reduced and capped to {actual_corner_radius}px")

        alignment = text_data.get('align', 'left')
        vertical_align = text_data.get('verticalAlign', 'top') # Added for vertical alignment
        line_height_multiplier = text_data.get('lineHeight', 1.2)

        words = text.split(' ') # Split by space, assumes simple space separation
        wrapped_lines = []
        current_line = ""
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if not current_line or pil_font.getlength(test_line) <= element_width:
                current_line = test_line
            else:
                if current_line: # Add the line that was too long for the new word
                    wrapped_lines.append(current_line)
                current_line = word # New word starts a new line
        if current_line:
            wrapped_lines.append(current_line)

        if not wrapped_lines:
            logger.debug(f"Text ID {element_id}: No lines after wrapping (text: '{text}'), returning blank canvas.")
            return local_canvas

        # Calculate line height based on font metrics
        try:
            # Using getbbox for a character with ascenders and descenders to estimate line height
            # Pillow's getsize/getlength is for width, getbbox includes vertical extent for a string.
            # For a more accurate line_height, especially across fonts, one might need more complex metrics.
            # Example: textbbox on a character like 'Agy' gives (left, top, right, bottom)
            # where top is negative for ascenders relative to baseline, bottom positive for descenders.
            # Height of the text content itself is bbox[3] - bbox[1].
            bbox_metrics = pil_font.getbbox("Agy") 
            text_content_height = bbox_metrics[3] - bbox_metrics[1] # Height of actual glyphs
            line_height_px = text_content_height * line_height_multiplier
        except (AttributeError, TypeError, IndexError):
            logger.warning(f"Text ID {element_id}: Could not get precise font bbox metrics. Using fontSize * multiplier for line_height.")
            line_height_px = font_size * line_height_multiplier
        line_height_px = max(1, int(line_height_px)) # Ensure line height is at least 1

        total_text_block_height = line_height_px * len(wrapped_lines)

        # Determine starting y position based on vertical alignment
        current_y = 0 # Default for top alignment
        if vertical_align == 'middle':
            current_y = (element_height - total_text_block_height) / 2
        elif vertical_align == 'bottom':
            current_y = element_height - total_text_block_height
        
        current_y = max(0, current_y) # Ensure drawing doesn't start outside the top of local_canvas

        # Draw text background for all lines first to ensure consistent order
        if text_data.get('backgroundEnabled', False) and parsed_bg_color:
            for line_idx, line in enumerate(wrapped_lines):
                if not line.strip(): # Skip empty lines
                    continue
                
                line_width = pil_font.getlength(line)
                line_x = 0 # Default for left alignment
                if alignment == 'center':
                    line_x = (element_width - line_width) / 2
                elif alignment == 'right':
                    line_x = element_width - line_width
                
                line_x = max(0, line_x) # Ensure drawing doesn't start outside the left of canvas
                line_y = current_y + line_idx * line_height_px
                
                # Get bbox of the text itself, anchored at its drawing position
                try:
                    text_actual_bbox = draw.textbbox((line_x, line_y), line, font=pil_font, anchor="lt")
                except AttributeError: # Fallback for older Pillow
                    text_actual_bbox = (line_x, line_y, line_x + line_width, line_y + text_content_height)
                
                # Determine background box with padding
                bg_x0 = text_actual_bbox[0] - actual_padding
                bg_y0 = text_actual_bbox[1] - actual_padding
                bg_x1 = text_actual_bbox[2] + actual_padding
                bg_y1 = text_actual_bbox[3] + actual_padding
                
                # Clip to element bounds
                bg_coords = (
                    max(0, bg_x0),
                    max(0, bg_y0),
                    min(element_width, bg_x1),
                    min(element_height, bg_y1)
                )
                
                # Only draw if the background has area
                if bg_coords[2] > bg_coords[0] and bg_coords[3] > bg_coords[1]:
                    # Draw the background with rounded corners
                    draw.rounded_rectangle(bg_coords, radius=actual_corner_radius, fill=parsed_bg_color)
                    logger.debug(f"Text ID {element_id}: Drew background for line {line_idx+1} at {bg_coords} with radius {actual_corner_radius} and color {parsed_bg_color}")

        # Now draw the text on top of backgrounds
        for line_idx, line in enumerate(wrapped_lines):
            if not line.strip(): # Skip empty lines
                if line_idx < len(wrapped_lines) - 1: # Only add line height if not the last line
                    current_y += line_height_px
                continue

            line_width = pil_font.getlength(line)
            line_x = 0 # Default for left alignment
            if alignment == 'center':
                line_x = (element_width - line_width) / 2
            elif alignment == 'right':
                line_x = element_width - line_width
            
            line_x = max(0, line_x) # Ensure drawing doesn't start outside the left of local_canvas
            
            # Draw the text line itself
            # The anchor='lt' means (line_x, current_y) is the top-left corner of the text bounding box.
            draw.text((line_x, current_y), line, font=pil_font, fill=parsed_fill_color, anchor="lt")
            current_y += line_height_px
            
            if current_y > element_height: # Stop if we're drawing past the element's allocated height
                logger.debug(f"Text ID {element_id}: Text content exceeds element height. Stopping rendering for this element.")
                break

        return local_canvas

    @staticmethod
    def render_text(image, text_data, font_mgr):
        """DEPRECATED: Render text directly onto a shared canvas. 
           Prefer render_text_to_image for layer-based processing.
        """
        logger.warning("Deprecated TextRenderer.render_text called. Consider switching to render_text_to_image.")
        # Simple passthrough to a modified version of old logic or raise error
        # For now, let's just log and attempt to use parts of the old logic if needed, 
        # but ideally this method should be removed or fully refactored if direct drawing is still required.

        # --- Start of adapted old logic (for context, will be simplified/removed) ---
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
            
            # Handle background opacity separately from the color's alpha
            bg_opacity = text_data.get('backgroundOpacity', 1.0)
            if parsed_bg_color and bg_opacity < 1.0:
                # If parsed_bg_color has alpha, adjust it by bg_opacity
                r, g, b, a = parsed_bg_color
                a = int(a * bg_opacity)
                parsed_bg_color = (r, g, b, a)
            
            padding_factor = text_data.get('backgroundPadding', 0.0)
            corner_radius_factor = text_data.get('backgroundCornerRadius', 0.0)

            # Calculate actual pixel values from factors and font_size
            actual_padding = padding_factor * font_size 
            actual_corner_radius = corner_radius_factor * font_size * 0.6  # Apply 0.6 multiplier for smaller radius
            
            # Ensure corner radius is not excessively large
            if actual_corner_radius > 0:
                 # Use more conservative cap similar to render_text_to_image method
                 max_radius = min(
                     actual_padding * 0.8,  # 80% of the padding
                     font_size / 3,         # 1/3 of the font size
                     text_data.get('width', font_size) / 4 if text_data.get('width') else font_size  # 1/4 of width if available
                 )
                 actual_corner_radius = min(actual_corner_radius, max_radius)

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