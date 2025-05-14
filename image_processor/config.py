"""
Configuration settings for the image processor.
Contains default values and configuration options.
"""

CONFIG = {
    'canvas': {
        'default_width': 1080,
        'default_height': 1080,
        'default_bg_color': (255, 255, 255, 255)  # RGBA white
    },
    'images': {
        'background_identifiers': ['NUdQFjNmk2'],  # IDs that are treated as backgrounds
        'default_quality': 'LANCZOS'
    },
    'fonts': {
        'default_font': 'Arial',
        'default_size': 12,
    },
    'debug': {
        'verbose_logging': True
    }
} 