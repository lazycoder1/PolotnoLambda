from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
import requests
from io import BytesIO
import os
import textwrap
import re
from collections import defaultdict
from utils.helpers import parse_color

class ImageProcessor:
    _font_map = None

    @classmethod
    def _build_font_map(cls):
        """Scan the 'fonts' directory and build a map of available fonts."""
        if cls._font_map is not None:
            return
            
        cls._font_map = defaultdict(dict)
        font_dir = 'fonts'
        if not os.path.isdir(font_dir):
            print(f"Warning: Font directory '{font_dir}' not found.")
            return

        print(f"Scanning '{font_dir}' for fonts...")
        found_count = 0
        for root, _, files in os.walk(font_dir):
            for filename in files:
                if filename.lower().endswith('.ttf'):
                    file_path = os.path.join(root, filename)
                    base_name = os.path.splitext(filename)[0]
                    
                    parts = re.split(r'[-_ ]', base_name)
                    family_parts = []
                    weight_style = 'normal'
                    
                    weight_keywords = {'thin', 'extralight', 'light', 'regular', 'medium', 'semibold', 'bold', 'extrabold', 'black', 'heavy'}
                    style_keywords = {'italic', 'oblique'}
                    
                    possible_weights = []
                    possible_styles = []

                    for part in parts:
                        part_lower = part.lower()
                        is_weight = part_lower in weight_keywords
                        is_style = part_lower in style_keywords
                        
                        if is_weight:
                            possible_weights.append(part_lower)
                        elif is_style:
                            possible_styles.append(part_lower)
                        elif not any(char.isdigit() for char in part):
                             family_parts.append(part)
                             
                    family_name = " ".join(family_parts) if family_parts else base_name
                    family_lower = family_name.lower()
                    
                    if possible_weights:
                         weight_style = possible_weights[-1]
                    elif 'regular' in family_lower:
                         weight_style = 'regular'
                    weight_lower = weight_style.lower()
                    if weight_lower == 'regular': weight_lower = 'normal'
                    
                    if family_lower and weight_lower:
                        cls._font_map[family_lower][weight_lower] = file_path
                        found_count += 1
                        
        print(f"Font scan complete. Found {found_count} font files.")

    @staticmethod
    def load_image_from_url(url):
        """Load image from URL and return PIL Image object"""
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        # Ensure the image has an alpha channel if it's not already in RGBA mode
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        return img

    @staticmethod
    def apply_image_effects(image, properties):
        """Apply various image effects based on properties"""
        # Ensure we're working with RGBA mode
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
            
        # Apply opacity
        if 'opacity' in properties and properties['opacity'] < 1:
            # Create a new alpha channel with the desired opacity
            alpha = image.split()[3]
            alpha = ImageEnhance.Brightness(alpha).enhance(properties['opacity'])
            image.putalpha(alpha)

        # Apply blur
        if properties.get('blurEnabled', False):
            # Split the image into RGB and alpha channels
            r, g, b, a = image.split()
            # Apply blur only to the RGB channels
            rgb = Image.merge('RGB', (r, g, b))
            rgb = rgb.filter(ImageFilter.GaussianBlur(radius=properties.get('blurRadius', 10)))
            # Recombine with the original alpha channel
            image = Image.merge('RGBA', (*rgb.split(), a))

        # Apply brightness
        if properties.get('brightnessEnabled', False):
            # Split the image into RGB and alpha channels
            r, g, b, a = image.split()
            # Apply brightness only to the RGB channels
            rgb = Image.merge('RGB', (r, g, b))
            enhancer = ImageEnhance.Brightness(rgb)
            rgb = enhancer.enhance(1 + properties.get('brightness', 0))
            # Recombine with the original alpha channel
            image = Image.merge('RGBA', (*rgb.split(), a))

        # Apply sepia
        if properties.get('sepiaEnabled', False):
            # Split the image into RGB and alpha channels
            r, g, b, a = image.split()
            # Apply sepia only to the RGB channels
            rgb = Image.merge('RGB', (r, g, b))
            width, height = rgb.size
            pixels = rgb.load()
            for py in range(height):
                for px in range(width):
                    r, g, b = pixels[px, py]
                    tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                    tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                    tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                    pixels[px, py] = (min(255, tr), min(255, tg), min(255, tb))
            # Recombine with the original alpha channel
            image = Image.merge('RGBA', (*rgb.split(), a))

        # Apply grayscale
        if properties.get('grayscaleEnabled', False):
            # Split the image into RGB and alpha channels
            r, g, b, a = image.split()
            # Apply grayscale only to the RGB channels
            rgb = Image.merge('RGB', (r, g, b))
            rgb = rgb.convert('L')
            # Recombine with the original alpha channel
            image = Image.merge('RGBA', (rgb, rgb, rgb, a))

        return image

    @staticmethod
    def create_rounded_corners(image, radius):
        """Create rounded corners for the image"""
        if radius <= 0:
            return image
        
        # Ensure we're working with RGBA mode
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
            
        # Create a mask with rounded corners
        mask = Image.new('L', image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), image.size], radius, fill=255)
        
        # Apply the mask to the alpha channel
        r, g, b, a = image.split()
        a = Image.composite(a, Image.new('L', image.size, 0), mask)
        image.putalpha(a)
        
        return image

    @staticmethod
    def rotate_image(image, angle):
        """Rotate image by given angle"""
        if angle == 0:
            return image
        # Ensure we're working with RGBA mode
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        return image.rotate(angle, expand=True, resample=Image.BICUBIC)

    @staticmethod
    def process_image(image_data):
        """Process a single image with all its properties"""
        try:
            # Load the image
            img = ImageProcessor.load_image_from_url(image_data['src'])
            
            # Get original dimensions for proper scaling
            orig_width, orig_height = img.size
            
            # Calculate target dimensions
            target_width = int(image_data['width'])
            target_height = int(image_data['height'])
            
            # Apply cropping if specified - relative to original image size
            if all(key in image_data for key in ['cropX', 'cropY', 'cropWidth', 'cropHeight']):
                crop_x = int(image_data['cropX'] * orig_width)
                crop_y = int(image_data['cropY'] * orig_height)
                crop_right = int((image_data['cropX'] + image_data['cropWidth']) * orig_width)
                crop_bottom = int((image_data['cropY'] + image_data['cropHeight']) * orig_height)
                # Ensure crop coordinates are valid
                crop_x = max(0, crop_x)
                crop_y = max(0, crop_y)
                crop_right = min(orig_width, crop_right)
                crop_bottom = min(orig_height, crop_bottom)
                if crop_right > crop_x and crop_bottom > crop_y:
                    img = img.crop((crop_x, crop_y, crop_right, crop_bottom))
                else:
                    print(f"Warning: Invalid crop dimensions for {image_data.get('src', 'unknown')}, skipping crop.")
            
            # Handle flip operations before resize
            if image_data.get('flipX', False):
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            if image_data.get('flipY', False):
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
            
            # --- Modified Resize Logic --- 
            is_background_image = image_data.get('id') == 'NUdQFjNmk2'
            keep_ratio_json = image_data.get('keepRatio', True)
            
            if is_background_image:
                # Background: Scale to fit canvas height, maintaining aspect ratio
                canvas_height = 1080
                aspect_ratio = img.width / img.height
                new_height = canvas_height
                new_width = int(new_height * aspect_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            elif keep_ratio_json:
                # Non-background, keepRatio=True: Fit within element dimensions, maintain aspect ratio
                img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            else:
                # Non-background, keepRatio=False: Resize exactly to element dimensions (may distort)
                img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            # --- End Modified Resize Logic ---
            
            # Apply rotation (on the potentially smaller, aspect-preserved image)
            if image_data.get('rotation', 0) != 0:
                img = ImageProcessor.rotate_image(img, image_data.get('rotation', 0))
            
            # Apply corner radius
            if image_data.get('cornerRadius', 0) > 0:
                img = ImageProcessor.create_rounded_corners(img, image_data.get('cornerRadius', 0))
            
            # Apply various effects
            img = ImageProcessor.apply_image_effects(img, image_data)
            
            # Calculate position based on JSON
            x = int(image_data['x'])
            y = int(image_data['y'])
            
            return img, (x, y)
            
        except Exception as e:
            raise Exception(f"Error processing image {image_data.get('src', 'unknown')}: {str(e)}")

    @staticmethod
    def _contains_devanagari(text):
        """Check if the text contains characters in the Devanagari Unicode range."""
        # Devanagari range: U+0900 to U+097F
        for char in text:
            if '\u0900' <= char <= '\u097F':
                return True
        return False

    @staticmethod
    def process_text(text_data, draw):
        """Process and draw text elements with wrapping, background, using dynamic font map and fallbacks."""
        ImageProcessor._build_font_map()
        
        try:
            # --- Get Properties --- 
            text = text_data.get('text', '')
            if not text: return # Nothing to draw
            
            x = int(text_data['x'])
            y = int(text_data['y'])
            elem_width = int(text_data.get('width', 100)) # Element's defined width
            font_size = int(text_data.get('fontSize', 12))
            req_family = text_data.get('fontFamily', 'Arial').lower()
            req_weight = text_data.get('fontWeight', 'normal').lower()
            if req_weight == 'regular': req_weight = 'normal'
            font_color_str = text_data.get('fill', 'black')
            line_height_multiplier = text_data.get('lineHeight', 1.2)
            alignment = text_data.get('align', 'left')
            
            bg_enabled = text_data.get('backgroundEnabled', False)
            bg_color_str = text_data.get('backgroundColor', '#000000')
            bg_opacity = text_data.get('backgroundOpacity', 1.0)
            bg_corner_radius = int(text_data.get('backgroundCornerRadius', 0))
            bg_padding = int(text_data.get('backgroundPadding', 0))
            # --- End Properties --- 

            # --- Font Selection & Loading (as before) --- 
            font = None
            font_path = None
            font_source_info = "default"
            needs_devanagari = ImageProcessor._contains_devanagari(text)
            fallback_family = "notosansdevanagari"
            
            # Determine the effective font family AND weight to use
            effective_family = req_family
            effective_weight = req_weight # Start with requested weight
            
            if needs_devanagari:
                # Try to use 'light' for Devanagari, fallback to 'normal'
                devanagari_preferred_weight = 'light' 
                effective_weight = devanagari_preferred_weight
                # Check if the fallback font exists in our map
                if ImageProcessor._font_map and fallback_family in ImageProcessor._font_map:
                    effective_family = fallback_family # Override requested family
                    # Verify preferred weight exists, otherwise use normal
                    if devanagari_preferred_weight not in ImageProcessor._font_map[fallback_family]:
                        effective_weight = 'normal' # Fallback to normal if light isn't mapped
                        
                    # print(f"Info: Devanagari detected. Using family '{effective_family}' and effective weight '{effective_weight}'")
                else:
                    # Fallback font family not found, still try to use preferred weight with original family (unlikely to work)
                    print(f"Warning: Devanagari needs '{fallback_family}' but not found. Using '{req_family}' (attempting weight '{effective_weight}').")
            
            # --- Font Loading Logic (using effective_family and effective_weight) --- 
            # 1. Look up effective font in map
            if ImageProcessor._font_map and effective_family in ImageProcessor._font_map:
                family_weights = ImageProcessor._font_map[effective_family]
                # Try the determined effective weight first
                if effective_weight in family_weights:
                    font_path = family_weights[effective_weight]
                    font_source_info = f"map ({effective_family} {effective_weight})"
                # Fallback to 'normal' within the effective family if specific/light weight wasn't found
                elif 'normal' in family_weights:
                    font_path = family_weights['normal']
                    font_source_info = f"map ({effective_family} normal fallback for {effective_weight})"
                else: # Family exists, but required/normal weights don't
                    font_path = next(iter(family_weights.values()), None) # Try any weight
                    if font_path: font_source_info = f"map ({effective_family} other weight fallback)"
                    
            # 2. Try loading from the determined path
            if font_path: 
                try: font = ImageFont.truetype(font_path, font_size)
                except Exception as e: print(f"Error loading font '{font_path}' ({font_source_info}): {e}"); font = None

            # 3. Fallback to system fonts (use effective weight here too)
            if font is None: 
                 try: 
                     # Try effective weight first, then normal/regular, then base
                     system_font_name_w = f"{req_family}-{effective_weight.capitalize()}.ttf"
                     system_font_name_r = f"{req_family}-Regular.ttf"
                     system_font_name_n = f"{req_family}-Normal.ttf"
                     system_font_name_b = f"{req_family}.ttf"
                     
                     potential_system_paths = []
                     potential_system_paths.append(system_font_name_w)
                     if effective_weight != 'normal': # Avoid duplicates if weight is normal
                         potential_system_paths.append(system_font_name_n)
                         potential_system_paths.append(system_font_name_r)
                     potential_system_paths.append(system_font_name_b)
                     
                     for sys_path_attempt in list(dict.fromkeys(potential_system_paths)): # Unique paths
                         try: 
                             font = ImageFont.truetype(sys_path_attempt, font_size)
                             font_source_info = f"system ({sys_path_attempt})"
                             break # Found one
                         except IOError: 
                             continue # Try next path
                             
                 except Exception: # Catch potential errors in path generation/lookup
                      pass 

            # 4. Final fallback to default
            if font is None: 
                print(f"Warning: Font '{req_family}' (Weight: {req_weight}) not found. Using default."); font = ImageFont.load_default(); font_source_info = "Pillow default"
            # --- End Font Loading --- 

            # --- Text Wrapping & Metrics (Pixel Width Based) --- 
            words = text.split()
            if not words: return # Nothing to draw
            
            wrapped_lines = []
            current_line = ""
            space_width = font.getlength(" ")
            # Allow lines to be slightly longer (e.g., 5% over element width) before breaking
            wrapping_width_tolerance = 1.05 
            max_line_pixel_width = elem_width * wrapping_width_tolerance
            
            for word in words:
                word_width = font.getlength(word)
                
                # If the word itself is wider than the tolerant width, handle it
                if word_width > max_line_pixel_width:
                    # If there's already text on the current line, add it first
                    if current_line:
                        wrapped_lines.append(current_line)
                        current_line = ""
                    # Break the long word (basic approach - add char by char)
                    temp_word_line = ""
                    for char in word:
                        char_width = font.getlength(char)
                        # Use max_line_pixel_width for breaking long words too
                        if font.getlength(temp_word_line) + char_width <= max_line_pixel_width:
                            temp_word_line += char
                        else:
                            if temp_word_line:
                                wrapped_lines.append(temp_word_line)
                            temp_word_line = char 
                    if temp_word_line:
                         wrapped_lines.append(temp_word_line)
                    continue 

                # Check if adding the next word exceeds the tolerant width
                potential_line = current_line + (" " if current_line else "") + word
                potential_width = font.getlength(potential_line)
                
                if potential_width <= max_line_pixel_width:
                    current_line = potential_line # Add word to current line
                else:
                    # Finish the current line (if not empty) and start new one
                    if current_line:
                        wrapped_lines.append(current_line)
                    current_line = word # Start new line with the current word
            
            # Add the last line if it has content
            if current_line:
                wrapped_lines.append(current_line)

            if not wrapped_lines: return # No lines produced
            
            try: # Calculate line height 
                 bbox = font.getbbox("Agy")
                 text_line_height = (bbox[3] - bbox[1]) * line_height_multiplier
            except AttributeError: 
                 text_line_height = font_size * line_height_multiplier
                 
            line_metrics = [(line, font.getlength(line)) for line in wrapped_lines]
            max_line_width = max(m[1] for m in line_metrics) if line_metrics else 0
            text_block_height = len(wrapped_lines) * text_line_height
            # --- End Metrics --- 
            
            # --- Calculate Actual Text Block Position --- 
            actual_text_x = x
            if alignment == 'center':
                actual_text_x = x + (elem_width - max_line_width) / 2
            elif alignment == 'right':
                actual_text_x = x + elem_width - max_line_width
            actual_text_y = y # Top of the text block
            # --- End Position Calc --- 

            # --- Draw Background (if enabled) --- 
            if bg_enabled:
                bg_color_parsed = parse_color(bg_color_str)
                if bg_color_parsed:
                    final_alpha = int(bg_color_parsed[3] * bg_opacity)
                    final_bg_color = (bg_color_parsed[0], bg_color_parsed[1], bg_color_parsed[2], final_alpha)
                    
                    # Background coordinates based on actual text block bounds + padding
                    bg_x0 = actual_text_x - bg_padding
                    bg_y0 = actual_text_y - bg_padding
                    bg_x1 = actual_text_x + max_line_width + bg_padding
                    bg_y1 = actual_text_y + text_block_height + bg_padding
                    
                    if bg_corner_radius > 0:
                        draw.rounded_rectangle([bg_x0, bg_y0, bg_x1, bg_y1], radius=bg_corner_radius, fill=final_bg_color)
                    else:
                        draw.rectangle([bg_x0, bg_y0, bg_x1, bg_y1], fill=final_bg_color)
                else:
                    print(f"Warning: Could not parse background color '{bg_color_str}'")
            # --- End Draw Background --- 

            # --- Draw Text --- 
            parsed_fill_color = parse_color(font_color_str)
            if parsed_fill_color is None: 
                 print(f"Error: Invalid text fill '{font_color_str}'. Skipping."); return
                 
            current_y = actual_text_y # Start drawing from the calculated top
            for i, (line, line_width) in enumerate(line_metrics):
                # Calculate x based on alignment for *this specific line*
                line_x = actual_text_x # Default for left align
                if alignment == 'center':
                     line_x = x + (elem_width - line_width) / 2 # Center within element width
                elif alignment == 'right':
                     line_x = x + elem_width - line_width # Right align within element width
                
                draw.text((int(line_x), int(current_y)), line, font=font, fill=parsed_fill_color)
                current_y += text_line_height
            # --- End Draw Text --- 
            
        except Exception as e:
            print(f"Error processing text element ID {text_data.get('id')}: {str(e)}")

    @staticmethod
    def process_figure(figure_data, draw):
        """Process and draw figure elements"""
        element_id = figure_data.get('id', 'N/A') # Get ID for logging
        print(f"DEBUG: Processing figure ID: {element_id}") # <<< DEBUG PRINT
        try:
            x = int(figure_data['x'])
            y = int(figure_data['y'])
            width = int(figure_data['width'])
            height = int(figure_data['height'])
            fill_color_str = figure_data.get('fill', 'black')
            corner_radius = figure_data.get('cornerRadius', 0)
            sub_type = figure_data.get('subType', 'rect') # Get subtype
            
            # Parse the fill color
            parsed_fill_color = parse_color(fill_color_str)
            if parsed_fill_color is None:
                 print(f"Error: Invalid figure fill color format '{fill_color_str}' for ID {element_id}. Skipping figure.")
                 return 
            
            if sub_type == 'rect':
                coords = [x, y, x + width, y + height]
                print(f"DEBUG: Drawing rect for {element_id} at {coords} with radius {corner_radius}") # <<< DEBUG PRINT
                if corner_radius > 0:
                    draw.rounded_rectangle(coords, radius=corner_radius, fill=parsed_fill_color)
                else:
                    draw.rectangle(coords, fill=parsed_fill_color)
            else:
                 print(f"Warning: Unsupported figure subType '{sub_type}' for ID {element_id}. Skipping.")
                    
        except Exception as e:
            print(f"Error processing figure ID {element_id}: {str(e)}")

    @staticmethod
    def combine_images(json_data):
        """Combine all elements from JSON data into a single image, rendering in JSON array order."""
        # Create a blank canvas with white background
        width = int(json_data['width'])
        height = int(json_data['height'])
        canvas = Image.new('RGBA', (width, height), 'white')
        # Create a single Draw object for figures and text
        draw = ImageDraw.Draw(canvas)
        
        for page in json_data['pages']:
            if 'children' not in page:
                continue
                
            # Iterate through children in the order they appear in the JSON
            for child in page['children']:
                element_type = child.get('type')
                element_id = child.get('id', 'N/A') # For error reporting
                
                try:
                    if element_type == 'figure':
                        ImageProcessor.process_figure(child, draw)
                    elif element_type == 'image':
                        img, position = ImageProcessor.process_image(child)
                        # Ensure image has alpha channel for consistent pasting
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                        # Paste using alpha channel as mask
                        canvas.paste(img, position, img) 
                    elif element_type == 'text':
                        # Draw text directly using the main draw object
                        ImageProcessor.process_text(child, draw)
                    # else: ignore unknown types
                        
                except Exception as e:
                    print(f"Error processing element (ID: {element_id}, Type: {element_type}): {str(e)}")
            
        # No need to explicitly delete draw object here
        return canvas 