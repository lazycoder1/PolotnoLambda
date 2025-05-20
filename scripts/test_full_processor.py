#!/usr/bin/env python
"""
Test script for verifying the full image processor pipeline with the polotno.json file.
This script processes a complete JSON file through the entire pipeline.
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

# Define absolute paths for input files
POLOTNO_JSON_PATH = ROOT_DIR / "samples" / "sample-json" / "polotno.json"

from image_processor.processor import ImageProcessor
from image_processor.logger import get_logger

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = get_logger(__name__)

def load_json_file(file_path):
    """Load and parse a JSON file"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {e}")
        return None

def create_test_json_with_figure():
    """Create a test JSON file that includes a figure element with cropping"""
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
                    # Background image with cropWidth < 1.0 (width-constrained)
                    {
                        "id": "background-image",
                        "type": "image",
                        "x": 0,
                        "y": 0,
                        "width": 1080,
                        "height": 1080,
                        "src": "https://images.unsplash.com/photo-1590874103328-eac38a683ce7?w=800&auto=format&fit=crop&q=60",
                        "cropX": 0.1273148148148149,
                        "cropY": 0,
                        "cropWidth": 0.7453703703703701,
                        "cropHeight": 1,
                        "opacity": 1,
                        "visible": True
                    },
                    # Figure element (circle) with cropping
                    {
                        "id": "discount-circle",
                        "type": "figure",
                        "subType": "circle",
                        "x": 800,
                        "y": 800,
                        "width": 200,
                        "height": 200,
                        "fill": "rgba(255,0,0,0.8)",
                        "stroke": "#FFFFFF",
                        "strokeWidth": 5,
                        "cropX": 0.1,
                        "cropY": 0.1,
                        "cropWidth": 0.8,
                        "cropHeight": 0.8,
                        "opacity": 1,
                        "visible": True
                    },
                    # Figure element (rectangle with rounded corners)
                    {
                        "id": "info-box",
                        "type": "figure",
                        "subType": "rect",
                        "x": 50,
                        "y": 50,
                        "width": 400,
                        "height": 200,
                        "fill": "rgba(0,0,0,0.6)",
                        "stroke": "#FFFFFF",
                        "strokeWidth": 2,
                        "cornerRadius": 20,
                        "opacity": 0.9,
                        "visible": True
                    },
                    # Title text
                    {
                        "id": "title-text",
                        "type": "text",
                        "x": 80,
                        "y": 100,
                        "width": 340,
                        "height": 100,
                        "text": "Product Title",
                        "fontSize": 40,
                        "fontFamily": "Roboto",
                        "fontWeight": "bold",
                        "fill": "white",
                        "align": "center",
                        "opacity": 1,
                        "visible": True
                    },
                    # Discount text
                    {
                        "id": "discount-text",
                        "type": "text",
                        "x": 820,
                        "y": 880,
                        "width": 160,
                        "height": 60,
                        "text": "25% OFF",
                        "fontSize": 26,
                        "fontFamily": "Roboto",
                        "fontWeight": "bold",
                        "fill": "white",
                        "align": "center",
                        "opacity": 1,
                        "visible": True
                    }
                ]
            }
        ]
    }
    return test_json

def test_full_processor(json_file_path=None, output_dir="test_output", use_custom_json=False):
    """
    Test the full image processor pipeline
    
    Args:
        json_file_path: Path to the JSON file to process (None if using custom JSON)
        output_dir: Directory to save output images
        use_custom_json: Whether to use a custom JSON with figure elements
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the JSON file or create a custom one
    if use_custom_json:
        logger.info("Using custom JSON with figure elements for testing")
        json_data = create_test_json_with_figure()
        test_type = "custom_with_figures"
    else:
        # Use the absolute path to polotno.json if no path is provided
        if json_file_path is None:
            json_file_path = POLOTNO_JSON_PATH
        
        logger.info(f"Loading JSON from {json_file_path}")
        json_data = load_json_file(json_file_path)
        if not json_data:
            logger.error("Failed to load JSON data. Exiting.")
            return False, None
        
        logger.info(f"Successfully loaded JSON data from {json_file_path}")
        test_type = "polotno"
    
    # Save a copy of the input JSON for reference
    json_path = os.path.join(output_dir, f"{test_type}_input.json")
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    logger.info(f"Saved JSON to {json_path}")
    
    # Process the JSON using the full image processor pipeline
    logger.info("Initializing ImageProcessor...")
    processor = ImageProcessor()
    
    logger.info("Processing JSON through the full pipeline...")
    output_image, errors = processor.combine_images(json_data)
    
    # Check for errors
    if errors:
        logger.warning(f"Processing completed with {len(errors)} errors:")
        for error in errors:
            logger.warning(f"Error: {error}")
    
    # Save the output image
    output_path = os.path.join(output_dir, f"{test_type}_output.png")
    output_image.save(output_path)
    logger.info(f"Saved processed image to {output_path}")
    
    # Display image dimensions
    logger.info(f"Output image dimensions: {output_image.size[0]}x{output_image.size[1]}")
    
    # Get summary of elements processed
    if 'pages' in json_data and json_data['pages']:
        page = json_data['pages'][0]
        if 'children' in page:
            elements_by_type = {}
            for child in page['children']:
                element_type = child.get('type', 'unknown')
                elements_by_type[element_type] = elements_by_type.get(element_type, 0) + 1
            
            logger.info("Elements processed by type:")
            for element_type, count in elements_by_type.items():
                logger.info(f"  - {element_type}: {count}")
    
    logger.info("Test completed successfully")
    return True, output_path

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test the full image processor pipeline")
    parser.add_argument("--json", "-j", default=None, 
                        help=f"Path to the JSON file to test (default: {POLOTNO_JSON_PATH})")
    parser.add_argument("--output", "-o", default="test_output", 
                        help="Directory to save output images (default: test_output)")
    parser.add_argument("--custom", "-c", action="store_true",
                        help="Use a custom JSON with figure elements instead of loading from file")
    args = parser.parse_args()
    
    if args.custom:
        success, output_path = test_full_processor(output_dir=args.output, use_custom_json=True)
    else:
        success, output_path = test_full_processor(args.json, args.output)
    
    if success:
        logger.info(f"Full processing test succeeded. Output image: {output_path}")
        
        # Try to display the image if running in an interactive environment
        try:
            if "DISPLAY" in os.environ or sys.platform == "darwin":
                output_image = Image.open(output_path)
                output_image.show()
        except Exception as e:
            logger.warning(f"Could not display image: {e}")
    else:
        logger.error("Full processing test failed")
        sys.exit(1) 