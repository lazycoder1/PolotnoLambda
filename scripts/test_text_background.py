#!/usr/bin/env python
"""
Test script for verifying text background properties (opacity, corner radius, padding)
"""

import os
import sys
import json
import logging
from PIL import Image
from pathlib import Path

# Add the project root to the path so we can import our modules
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from image_processor.processor import ImageProcessor
from image_processor.logger import get_logger
from image_processor.text_renderer import TextRenderer
from image_processor.font_manager import FontManager

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = get_logger(__name__)

def create_test_json_with_text_backgrounds():
    """Create a test JSON file that includes text elements with various background settings"""
    test_json = {
        "width": 1080,
        "height": 1080,
        "pages": [
            {
                "id": "test-page",
                "width": 1080,
                "height": 1080,
                "background": "white",
                "children": [
                    # Text with full opacity background
                    {
                        "id": "text-full-opacity",
                        "type": "text",
                        "x": 40,
                        "y": 40,
                        "width": 1000,
                        "height": 120,
                        "text": "Full Opacity Background (1.0)",
                        "fontSize": 60,
                        "fontFamily": "Roboto",
                        "fontWeight": "bold",
                        "fill": "white",
                        "align": "center",
                        "backgroundColor": "rgba(0,0,0,1.0)",
                        "backgroundEnabled": True,
                        "backgroundPadding": 0.2,
                        "backgroundCornerRadius": 0.2,
                        "backgroundOpacity": 1.0,
                        "opacity": 1,
                        "visible": True
                    },
                    # Text with 75% opacity background
                    {
                        "id": "text-75-opacity",
                        "type": "text",
                        "x": 40,
                        "y": 180,
                        "width": 1000,
                        "height": 120,
                        "text": "75% Opacity Background (0.75)",
                        "fontSize": 60,
                        "fontFamily": "Roboto",
                        "fontWeight": "bold",
                        "fill": "white",
                        "align": "center",
                        "backgroundColor": "rgba(0,0,0,1.0)",
                        "backgroundEnabled": True,
                        "backgroundPadding": 0.2,
                        "backgroundCornerRadius": 0.2,
                        "backgroundOpacity": 0.75,
                        "opacity": 1,
                        "visible": True
                    },
                    # Text with 50% opacity background
                    {
                        "id": "text-50-opacity",
                        "type": "text",
                        "x": 40,
                        "y": 320,
                        "width": 1000,
                        "height": 120,
                        "text": "50% Opacity Background (0.5)",
                        "fontSize": 60,
                        "fontFamily": "Roboto",
                        "fontWeight": "bold",
                        "fill": "white",
                        "align": "center",
                        "backgroundColor": "rgba(0,0,0,1.0)",
                        "backgroundEnabled": True,
                        "backgroundPadding": 0.2,
                        "backgroundCornerRadius": 0.2,
                        "backgroundOpacity": 0.5,
                        "opacity": 1,
                        "visible": True
                    },
                    # Text with 25% opacity background
                    {
                        "id": "text-25-opacity",
                        "type": "text",
                        "x": 40,
                        "y": 460,
                        "width": 1000,
                        "height": 120,
                        "text": "25% Opacity Background (0.25)",
                        "fontSize": 60,
                        "fontFamily": "Roboto",
                        "fontWeight": "bold",
                        "fill": "white",
                        "align": "center",
                        "backgroundColor": "rgba(0,0,0,1.0)",
                        "backgroundEnabled": True,
                        "backgroundPadding": 0.2,
                        "backgroundCornerRadius": 0.2,
                        "backgroundOpacity": 0.25,
                        "opacity": 1,
                        "visible": True
                    },
                    # Text with different corner radius values
                    {
                        "id": "text-corner-radius-0",
                        "type": "text",
                        "x": 40,
                        "y": 600,
                        "width": 500,
                        "height": 80,
                        "text": "Corner Radius 0",
                        "fontSize": 40,
                        "fontFamily": "Roboto",
                        "fontWeight": "bold",
                        "fill": "white",
                        "align": "center",
                        "backgroundColor": "rgba(255,0,0,1.0)",
                        "backgroundEnabled": True,
                        "backgroundPadding": 0.3,
                        "backgroundCornerRadius": 0,
                        "backgroundOpacity": 1.0,
                        "opacity": 1,
                        "visible": True
                    },
                    {
                        "id": "text-corner-radius-0.3",
                        "type": "text",
                        "x": 560,
                        "y": 600,
                        "width": 500,
                        "height": 80,
                        "text": "Corner Radius 0.3",
                        "fontSize": 40,
                        "fontFamily": "Roboto",
                        "fontWeight": "bold",
                        "fill": "white",
                        "align": "center",
                        "backgroundColor": "rgba(255,0,0,1.0)",
                        "backgroundEnabled": True,
                        "backgroundPadding": 0.3,
                        "backgroundCornerRadius": 0.3,
                        "backgroundOpacity": 1.0,
                        "opacity": 1,
                        "visible": True
                    },
                    # New test case with small corner radius
                    {
                        "id": "text-corner-radius-0.1",
                        "type": "text",
                        "x": 40,
                        "y": 650,
                        "width": 500,
                        "height": 40,
                        "text": "Corner Radius 0.1 (Reduced)",
                        "fontSize": 30,
                        "fontFamily": "Roboto",
                        "fontWeight": "bold",
                        "fill": "white",
                        "align": "center",
                        "backgroundColor": "rgba(255,0,0,1.0)",
                        "backgroundEnabled": True,
                        "backgroundPadding": 0.3,
                        "backgroundCornerRadius": 0.1,
                        "backgroundOpacity": 1.0,
                        "opacity": 1,
                        "visible": True
                    },
                    # Text with different padding values
                    {
                        "id": "text-padding-0.1",
                        "type": "text",
                        "x": 40,
                        "y": 700,
                        "width": 500,
                        "height": 80,
                        "text": "Padding 0.1",
                        "fontSize": 40,
                        "fontFamily": "Roboto",
                        "fontWeight": "bold",
                        "fill": "white",
                        "align": "center",
                        "backgroundColor": "rgba(0,128,0,1.0)",
                        "backgroundEnabled": True,
                        "backgroundPadding": 0.1,
                        "backgroundCornerRadius": 0.2,
                        "backgroundOpacity": 1.0,
                        "opacity": 1,
                        "visible": True
                    },
                    {
                        "id": "text-padding-0.5",
                        "type": "text",
                        "x": 560,
                        "y": 700,
                        "width": 500,
                        "height": 80,
                        "text": "Padding 0.5",
                        "fontSize": 40,
                        "fontFamily": "Roboto",
                        "fontWeight": "bold",
                        "fill": "white",
                        "align": "center",
                        "backgroundColor": "rgba(0,128,0,1.0)",
                        "backgroundEnabled": True,
                        "backgroundPadding": 0.5,
                        "backgroundCornerRadius": 0.2,
                        "backgroundOpacity": 1.0,
                        "opacity": 1,
                        "visible": True
                    },
                    # Multiline text with background
                    {
                        "id": "text-multiline",
                        "type": "text",
                        "x": 40,
                        "y": 800,
                        "width": 1000,
                        "height": 200,
                        "text": "This is a multiline text that demonstrates how backgrounds are applied to wrapped text. Each line should have its own background with consistent padding and corner radius.",
                        "fontSize": 40,
                        "fontFamily": "Roboto",
                        "fontWeight": "normal",
                        "fill": "white",
                        "align": "center",
                        "backgroundColor": "rgba(0,0,255,0.8)",
                        "backgroundEnabled": True,
                        "backgroundPadding": 0.3,
                        "backgroundCornerRadius": 0.3,
                        "backgroundOpacity": 0.8,
                        "opacity": 1,
                        "visible": True
                    }
                ]
            }
        ]
    }
    return test_json

def test_text_background_rendering(output_dir="test_output"):
    """
    Test text background rendering with various opacity, corner radius, and padding settings
    
    Args:
        output_dir: Directory to save output images
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create test JSON
    test_json = create_test_json_with_text_backgrounds()
    
    # Save JSON to file for reference
    json_path = os.path.join(output_dir, "text_background_test_input.json")
    with open(json_path, 'w') as f:
        json.dump(test_json, f, indent=2)
    logger.info(f"Saved test JSON to {json_path}")
    
    # Initialize FontManager
    font_mgr = FontManager()
    
    # 1. Test individual text element rendering
    logger.info("Testing individual text element rendering...")
    for idx, child in enumerate(test_json['pages'][0]['children']):
        if child['type'] == 'text':
            element_id = child['id']
            logger.info(f"Rendering text element {element_id}")
            
            # Render text element
            text_image = TextRenderer.render_text_to_image(child, font_mgr)
            
            # Save the rendered text element
            element_output_path = os.path.join(output_dir, f"text_element_{idx}_{element_id}.png")
            text_image.save(element_output_path)
            logger.info(f"Saved text element to {element_output_path}")
    
    # 2. Test full image processor pipeline
    logger.info("Testing full image processor pipeline...")
    processor = ImageProcessor()
    
    output_image, errors = processor.combine_images(test_json)
    
    # Check for errors
    if errors:
        logger.warning(f"Processing completed with {len(errors)} errors:")
        for error in errors:
            logger.warning(f"Error: {error}")
    
    # Save the output image
    output_path = os.path.join(output_dir, "text_background_test_output.png")
    output_image.save(output_path)
    logger.info(f"Saved full processed image to {output_path}")
    
    logger.info("Test completed successfully")
    return True, output_path

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test text background rendering")
    parser.add_argument("--output", "-o", default="test_output", 
                        help="Directory to save output images (default: test_output)")
    args = parser.parse_args()
    
    success, output_path = test_text_background_rendering(args.output)
    
    if success:
        logger.info(f"Text background test succeeded. Output image: {output_path}")
        
        # Try to display the image if running in an interactive environment
        try:
            if "DISPLAY" in os.environ or sys.platform == "darwin":
                output_image = Image.open(output_path)
                output_image.show()
        except Exception as e:
            logger.warning(f"Could not display image: {e}")
    else:
        logger.error("Text background test failed")
        sys.exit(1) 