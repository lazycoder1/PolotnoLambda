"""
Logging module for the image processor.
Provides consistent logging across the application.
"""

import logging
from .config import CONFIG

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if CONFIG['debug']['verbose_logging'] else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_logger(name):
    """Get a logger with the specified name."""
    return logging.getLogger(name) 