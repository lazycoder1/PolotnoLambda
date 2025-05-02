from image_processor.processor import ImageProcessor
from utils.helpers import load_json_file, save_image, validate_json_structure
import os

def main():
    try:
        input_json_path = 'samples/sample-json/sample-4.json'
        output_dir = 'samples/sample-image-outputs'
        
        # Create output directory if it doesn't exist (belt-and-suspenders)
        os.makedirs(output_dir, exist_ok=True)
        
        # Determine output filename
        base_name = os.path.basename(input_json_path)
        file_name_without_ext = os.path.splitext(base_name)[0]
        output_image_path = os.path.join(output_dir, f"{file_name_without_ext}.png")
        
        # Load JSON data
        json_data = load_json_file(input_json_path)
        
        # Validate JSON structure
        if not validate_json_structure(json_data):
            raise ValueError("Invalid JSON structure")
        
        # Combine images
        result_image = ImageProcessor.combine_images(json_data)
        
        # Save the result
        saved_path = save_image(result_image, output_image_path)
        print(f"Image saved as {saved_path}")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
