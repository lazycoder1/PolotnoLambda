"""
Figure renderer module.
Handles processing and rendering of various shapes and figures.
"""

from typing import Dict, Any, Tuple
from utils.helpers import parse_color
from image_processor.logger import get_logger

logger = get_logger(__name__)

def process_figure(figure_data: Dict[str, Any], draw) -> None:
    """Process and draw figure elements"""
    element_id = figure_data.get('id', 'N/A')
    logger.debug(f"Processing figure ID: {element_id}")
    
    try:
        # Validate input
        required_fields = ['x', 'y', 'width', 'height']
        for field in required_fields:
            if field not in figure_data:
                raise ValueError(f"Missing required field '{field}' in figure data")
        
        # Get position and dimensions
        x = int(figure_data['x'])
        y = int(figure_data['y'])
        width = int(figure_data['width'])
        height = int(figure_data['height'])
        
        # Get appearance properties
        fill_color_str = figure_data.get('fill', 'black')
        corner_radius = figure_data.get('cornerRadius', 0)
        sub_type = figure_data.get('subType', 'rect')
        
        # Parse the fill color
        parsed_fill_color = parse_color(fill_color_str)
        logger.debug(f"Parsed fill color for {element_id}: {parsed_fill_color}")
        
        if parsed_fill_color is None:
            logger.error(f"Invalid figure fill color format '{fill_color_str}' for ID {element_id}. Skipping figure.")
            return
        
        # Draw the figure based on sub_type
        if sub_type == 'rect':
            coords = [x, y, x + width, y + height]
            logger.debug(f"Drawing rectangle for {element_id} at {coords} with radius {corner_radius}")
            if corner_radius > 0:
                draw.rounded_rectangle(coords, radius=corner_radius, fill=parsed_fill_color)
            else:
                draw.rectangle(coords, fill=parsed_fill_color)
        elif sub_type == 'ellipse':
            coords = [x, y, x + width, y + height]
            draw.ellipse(coords, fill=parsed_fill_color)
        else:
            logger.warning(f"Unsupported figure subType '{sub_type}' for ID {element_id}. Skipping.")
                
    except Exception as e:
        logger.error(f"Error processing figure ID {element_id}: {str(e)}") 