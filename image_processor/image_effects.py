"""
Image effects module.
Handles various image transformations and effects like blur, brightness, etc.
"""

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

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

def rotate_image(image, angle):
    """Rotate image by given angle"""
    if angle == 0:
        return image
    # Ensure we're working with RGBA mode
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    return image.rotate(angle, expand=True, resample=Image.BICUBIC) 