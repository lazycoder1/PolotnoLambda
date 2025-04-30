import requests
import os
import logging # Use logging for better messages

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Font definitions: { Target Directory: { Filename: URL } }
FONTS_TO_DOWNLOAD = {
    'fonts': { # General fonts directory
        'Raleway-Normal.ttf': 'https://raw.githubusercontent.com/impallari/Raleway/master/fonts/TTF/Raleway-Regular.ttf', 
        'Raleway-Bold.ttf': 'https://raw.githubusercontent.com/impallari/Raleway/master/fonts/TTF/Raleway-Bold.ttf'
        # Add other general fonts here if needed
    },
    'fonts/NotoSansDevanagari': { # Specific directory for Noto Devanagari
        'NotoSansDevanagari-Regular.ttf': 'https://raw.githubusercontent.com/googlefonts/noto-fonts/main/fonts/NotoSansDevanagari/googlefonts/ttf/NotoSansDevanagari-Regular.ttf',
        'NotoSansDevanagari-Bold.ttf': 'https://raw.githubusercontent.com/googlefonts/noto-fonts/main/fonts/NotoSansDevanagari/googlefonts/ttf/NotoSansDevanagari-Bold.ttf'
    }
    # Add other font families in specific directories if desired
}

def download_font(url: str, target_path: str):
    """Downloads a single font file.
    Returns True on success, False on failure.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }
    try:
        # Ensure target directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        logging.info(f"Downloading {os.path.basename(target_path)} from {url}...")
        response = requests.get(url, headers=headers, stream=True, timeout=60) # Increased timeout
        response.raise_for_status() # Check for HTTP errors
        
        # Basic content type check (optional but good practice)
        content_type = response.headers.get('Content-Type', '')
        if 'font/ttf' not in content_type and 'application/octet-stream' not in content_type:
            logging.warning(f"Unexpected content type '{content_type}' for {target_path}. Attempting to save anyway.")
        
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(f"Successfully saved {os.path.basename(target_path)} to {target_path}")
        return True
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Error downloading {os.path.basename(target_path)}: {e}")
    except Exception as e:
        logging.error(f"An error occurred while saving {os.path.basename(target_path)}: {e}")
    return False

def download_and_setup_fonts():
    """Download and setup required fonts defined in FONTS_TO_DOWNLOAD."""
    
    total_fonts = sum(len(files) for files in FONTS_TO_DOWNLOAD.values())
    downloaded_count = 0
    failed_count = 0

    logging.info(f"Starting font download process for {total_fonts} file(s)...")

    for target_dir, files_to_download in FONTS_TO_DOWNLOAD.items():
        for filename, url in files_to_download.items():
            target_path = os.path.join(target_dir, filename)
            # Optional: Check if file already exists to avoid re-downloading
            # if os.path.exists(target_path):
            #     logging.info(f"Font '{filename}' already exists. Skipping download.")
            #     downloaded_count += 1 # Count existing as success
            #     continue 
            if download_font(url, target_path):
                downloaded_count += 1
            else:
                failed_count += 1

    logging.info("--- Font Download Summary ---")
    logging.info(f"Successfully downloaded/verified: {downloaded_count}/{total_fonts}")
    if failed_count > 0:
        logging.warning(f"Failed to download: {failed_count}/{total_fonts}")
    logging.info("---------------------------")

if __name__ == "__main__":
    download_and_setup_fonts() 