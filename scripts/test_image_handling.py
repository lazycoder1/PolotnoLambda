#!/usr/bin/env python
"""
Test script for verifying image handling logic with polotno.json
This script demonstrates the scaling and cropping approach documented in docs/image_handling.md
"""

import os
import sys
import json
import logging
from PIL import Image, ImageDraw
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from image_processor.image_handler import process_image
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

def test_image_handling(json_file_path, output_dir="test_output"):
    """
    Test the image handling logic using the given JSON file
    
    Args:
        json_file_path: Path to the JSON file containing image data
        output_dir: Directory to save output images
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the JSON file
    json_data = load_json_file(json_file_path)
    if not json_data:
        logger.error("Failed to load JSON data. Exiting.")
        return False
    
    logger.info(f"Successfully loaded JSON data from {json_file_path}")
    
    # Check if the JSON structure has pages and children
    if 'pages' not in json_data or not json_data['pages']:
        logger.error("No pages found in JSON data")
        return False
    
    # Get the first page
    page = json_data['pages'][0]
    if 'children' not in page or not page['children']:
        logger.error("No children found in the first page")
        return False
    
    # Find the first image element
    image_elements = [child for child in page['children'] if child.get('type') == 'image']
    if not image_elements:
        logger.error("No image elements found")
        return False
    
    # Process the first image element
    image_data = image_elements[0]
    logger.info(f"Processing image element with ID: {image_data.get('id')}")
    
    # Display original image information
    src_url = image_data.get('src')
    logger.info(f"Image source URL: {src_url}")
    logger.info(f"Crop parameters: cropX={image_data.get('cropX')}, cropY={image_data.get('cropY')}, "
                f"cropWidth={image_data.get('cropWidth')}, cropHeight={image_data.get('cropHeight')}")
    
    # Process the image
    processed_image, _ = process_image(image_data)
    if not processed_image:
        logger.error("Failed to process the image")
        return False
    
    # Save the processed image
    output_path = os.path.join(output_dir, "processed_image.png")
    processed_image.save(output_path)
    logger.info(f"Saved processed image to {output_path}")
    
    # Create a visualization to show the cropping
    logger.info("Creating visualization of the cropping process...")
    
    # Create the original scaled image with visible crop region
    vis_image_path = os.path.join(output_dir, "visualization.png")
    
    # Determine which dimension is constrained
    final_width = int(image_data.get('width', 1080))
    final_height = int(image_data.get('height', 1080))
    crop_width = image_data.get('cropWidth', 1.0)
    crop_height = image_data.get('cropHeight', 1.0)
    
    # Get the processed image size for comparison
    processed_width, processed_height = processed_image.size
    
    # Create a test image with grid lines and crop region
    if crop_width < 1.0 and crop_height == 1.0:
        # Width-constrained
        target_width = int(final_width / crop_width)
        # Calculate what the original target_height would be based on target_width
        # We'll create a visualization canvas of this size
        orig_vis_width = target_width
        orig_vis_height = target_width  # Square for better visualization
        
        # Calculate crop coordinates
        crop_x = int(image_data.get('cropX', 0) * target_width)
        crop_y = int(image_data.get('cropY', 0) * target_width)
        crop_region_width = int(crop_width * target_width)
        crop_region_height = final_height
    else:
        # Height-constrained or both constrained
        orig_vis_width = final_width
        orig_vis_height = final_height
        
        crop_x = int(image_data.get('cropX', 0) * orig_vis_width)
        crop_y = int(image_data.get('cropY', 0) * orig_vis_height)
        crop_region_width = final_width
        crop_region_height = final_height
    
    # Create a visualization canvas
    vis_image = Image.new('RGBA', (orig_vis_width, orig_vis_height), (230, 230, 230, 255))
    draw = ImageDraw.Draw(vis_image)
    
    # Draw grid lines
    for x in range(0, orig_vis_width, 50):
        draw.line([(x, 0), (x, orig_vis_height)], fill=(200, 200, 200, 128), width=1)
    for y in range(0, orig_vis_height, 50):
        draw.line([(0, y), (orig_vis_width, y)], fill=(200, 200, 200, 128), width=1)
    
    # Draw crop region
    draw.rectangle([crop_x, crop_y, crop_x + crop_region_width, crop_y + crop_region_height], 
                   outline=(255, 0, 0, 255), width=3)
    
    # Add text annotations
    if hasattr(draw, 'text'):
        # Draw text explaining dimensions
        draw.text((10, 10), f"Original URL: {src_url.split('?')[0]}", fill=(0, 0, 0, 255))
        draw.text((10, 30), f"Virtual canvas: {orig_vis_width}x{orig_vis_height}", fill=(0, 0, 0, 255))
        draw.text((10, 50), f"Crop region (red): {crop_region_width}x{crop_region_height}", fill=(255, 0, 0, 255))
        draw.text((10, 70), f"Starting at: ({crop_x}, {crop_y})", fill=(255, 0, 0, 255))
        draw.text((10, 90), f"Final output: {processed_width}x{processed_height}", fill=(0, 0, 255, 255))
    
    # Save the visualization
    vis_image.save(vis_image_path)
    logger.info(f"Saved visualization to {vis_image_path}")
    
    # Place the processed image next to the visualization for comparison
    comparison_image_path = os.path.join(output_dir, "comparison.png")
    comparison_width = orig_vis_width + processed_width + 20  # Add some padding
    comparison_height = max(orig_vis_height, processed_height)
    comparison_image = Image.new('RGBA', (comparison_width, comparison_height), (230, 230, 230, 255))
    
    # Paste the visualization
    comparison_image.paste(vis_image, (0, 0))
    
    # Paste the processed image
    comparison_image.paste(processed_image, (orig_vis_width + 20, 0), processed_image)
    
    # Draw a divider line
    draw = ImageDraw.Draw(comparison_image)
    draw.line([(orig_vis_width + 10, 0), (orig_vis_width + 10, comparison_height)], fill=(0, 0, 0, 255), width=2)
    
    # Save the comparison image
    comparison_image.save(comparison_image_path)
    logger.info(f"Saved comparison image to {comparison_image_path}")
    
    logger.info("Test completed successfully")
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test image handling logic with JSON file")
    parser.add_argument("--json", "-j", default="samples/sample-json/polotno.json", 
                        help="Path to the JSON file to test (default: samples/sample-json/polotno.json)")
    parser.add_argument("--output", "-o", default="test_output", 
                        help="Directory to save output images (default: test_output)")
    args = parser.parse_args()
    
    test_image_handling(args.json, args.output) 