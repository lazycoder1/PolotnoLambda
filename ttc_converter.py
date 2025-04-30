#!/usr/bin/env python3
"""
TTC to TTF Font Converter and Tester

This script provides two functions:
1. Test if Pillow can correctly load .ttc files for use with Hindi text
2. Convert .ttc files to .ttf files if needed

Usage:
- To test a .ttc file:
    python ttc_converter.py test /path/to/font.ttc
    
- To convert a .ttc file:
    python ttc_converter.py convert /path/to/font.ttc output_dir [--index 0]
    
- To convert all .ttc files in a directory:
    python ttc_converter.py convert-all /input/dir /output/dir
"""

import os
import sys
import argparse
import tempfile
import shutil
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

def test_ttc_font(ttc_path, text="नमस्ते दुनिया"):
    """Test if Pillow can load a .ttc font and render Hindi text with it"""
    print(f"Testing TTC font: {ttc_path}")
    
    # Try different indices if the font is a collection
    for index in range(5):  # Try at most 5 fonts in the collection
        try:
            # Try to load the font with this index
            font = ImageFont.truetype(ttc_path, size=36, index=index)
            
            # Create a sample image and render text
            img = Image.new('RGB', (600, 100), color='white')
            draw = ImageDraw.Draw(img)
            
            # Draw the text
            draw.text((20, 20), text, font=font, fill='black')
            
            # Save the test image to a temporary file
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"test_font_index_{index}.png")
            img.save(output_path)
            
            print(f"✅ Success! Font loaded with index {index}")
            print(f"Test image saved to: {output_path}")
            print(f"You can view this image to confirm the Hindi text is displayed correctly")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load font with index {index}: {e}")
    
    print("Could not load the TTC font with any index.")
    return False

def convert_ttc_to_ttf(ttc_path, output_dir, index=0):
    """Convert a .ttc file to a .ttf file"""
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Get the base filename
        basename = os.path.basename(ttc_path)
        name_without_ext = os.path.splitext(basename)[0]
        
        # Load the font with fontTools
        font = TTFont(ttc_path, fontNumber=index)
        
        # Determine output path
        output_path = os.path.join(output_dir, f"{name_without_ext}_index{index}.ttf")
        
        # Save as TTF
        font.save(output_path)
        
        print(f"✅ Converted {ttc_path} (index {index}) to {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        return None

def convert_all_ttc_in_dir(input_dir, output_dir):
    """Convert all .ttc files in a directory to .ttf files"""
    if not os.path.isdir(input_dir):
        print(f"❌ Input directory {input_dir} does not exist")
        return
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Find all .ttc files
    ttc_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) 
                if f.lower().endswith('.ttc')]
    
    if not ttc_files:
        print(f"❌ No .ttc files found in {input_dir}")
        return
    
    print(f"Found {len(ttc_files)} .ttc files")
    
    for ttc_path in ttc_files:
        # Try to determine how many fonts are in the collection
        try:
            for index in range(5):  # Try up to 5 fonts in each collection
                convert_ttc_to_ttf(ttc_path, output_dir, index)
        except Exception as e:
            print(f"Error processing {ttc_path}: {e}")

def modify_font_manager(ttf_paths):
    """Helper function to show how to update font_manager.py for the new TTF files"""
    if not ttf_paths:
        return
    
    print("\nTo use the converted TTF files, update your font_manager.py:")
    print("\n# Add these paths directly in the build_font_map method:")
    for i, path in enumerate(ttf_paths):
        weight = "bold" if "bold" in path.lower() else "normal"
        if "semi" in path.lower() or "medium" in path.lower():
            weight = "semibold"
        print(f'cls._font_map["kohinoordevanagari"]["{weight}"] = "{path}"')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TTC to TTF Font Converter and Tester")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test if a .ttc font works with Pillow")
    test_parser.add_argument("ttc_path", help="Path to the .ttc font file")
    test_parser.add_argument("--text", default="नमस्ते दुनिया", help="Hindi text to render")
    
    # Convert command
    convert_parser = subparsers.add_parser("convert", help="Convert a .ttc file to .ttf")
    convert_parser.add_argument("ttc_path", help="Path to the .ttc font file")
    convert_parser.add_argument("output_dir", help="Output directory for the .ttf file")
    convert_parser.add_argument("--index", type=int, default=0, help="Font index in the collection (default: 0)")
    
    # Convert-all command
    convert_all_parser = subparsers.add_parser("convert-all", help="Convert all .ttc files in a directory")
    convert_all_parser.add_argument("input_dir", help="Directory containing .ttc files")
    convert_all_parser.add_argument("output_dir", help="Output directory for the .ttf files")
    
    args = parser.parse_args()
    
    if args.command == "test":
        test_ttc_font(args.ttc_path, args.text)
    
    elif args.command == "convert":
        ttf_path = convert_ttc_to_ttf(args.ttc_path, args.output_dir, args.index)
        if ttf_path:
            modify_font_manager([ttf_path])
    
    elif args.command == "convert-all":
        convert_all_ttc_in_dir(args.input_dir, args.output_dir)
    
    else:
        parser.print_help() 