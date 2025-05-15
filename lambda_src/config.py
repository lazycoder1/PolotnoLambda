import os
import boto3
from image_processor.processor import ImageProcessor
from image_processor.logger import get_logger

logger = get_logger(__name__) # Logger for this config module

# --- AWS Clients ---
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')

# --- Environment Variables ---
# For SQS
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
DLQ_URL = os.environ.get('DLQ_URL') # For error logging, not directly used by code to send messages

# For Database
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT', '5432') # Default PostgreSQL port
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')

# For Auth0
AUTH0_DOMAIN = os.environ.get('AUTH0_DOMAIN')
AUTH0_AUDIENCE = os.environ.get('AUTH0_AUDIENCE')

# For S3 output (generated images)
S3_IMAGE_OUTPUT_BUCKET = os.environ.get('S3_IMAGE_OUTPUT_BUCKET')

# For ImageProcessor
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
FONT_S3_BUCKET = os.environ.get("FONT_S3_BUCKET")

# --- Global Variables / Initializers ---
db_connection_params = None
_image_proc_instance_singleton = None # Internal, use getter

def _load_db_credentials_from_env():
    """Loads DB credentials directly from environment variables."""
    global db_connection_params
    logger.info("Attempting to load DB credentials from environment variables...")
    
    # Log the values of the environment variables being read
    logger.info(f"Read DB_HOST: '{DB_HOST}'")
    logger.info(f"Read DB_PORT: '{DB_PORT}'")
    logger.info(f"Read DB_NAME: '{DB_NAME}'")
    logger.info(f"Read DB_USER: '{DB_USER}'")
    # Be cautious logging DB_PASSWORD, even in debug. For testing, you might log its presence/absence.
    logger.info(f"DB_PASSWORD is {'SET' if DB_PASSWORD else 'NOT SET'}")

    required_db_vars = {
        'DB_HOST': DB_HOST,
        'DB_NAME': DB_NAME,
        'DB_USER': DB_USER,
        'DB_PASSWORD': DB_PASSWORD
    }
    missing_vars = [key for key, value in required_db_vars.items() if not value]
    if missing_vars:
        err_msg = f"Missing required database environment variables: { ', '.join(missing_vars)}"
        logger.error(err_msg)
        # Ensure db_connection_params remains None or is cleared if partial load was attempted
        db_connection_params = None 
        raise ValueError(f"Incomplete database configuration. Missing: { ', '.join(missing_vars)}")

    try:
        db_connection_params = {
            "host": DB_HOST,
            "port": int(DB_PORT),
            "dbname": DB_NAME,
            "user": DB_USER,
            "password": DB_PASSWORD
        }
        safe_params_to_log = {k: (v if k != 'password' else '********') for k, v in db_connection_params.items()}
        logger.info(f"Database credentials successfully loaded and parsed. db_connection_params (password masked): {safe_params_to_log}")
    except ValueError as e: 
        err_msg = f"Invalid DB_PORT value: '{DB_PORT}'. Must be an integer. Error: {e}"
        logger.error(err_msg, exc_info=True)
        db_connection_params = None # Clear on error
        raise ValueError(f"Invalid DB_PORT: {e}")
    except Exception as e: 
        logger.error(f"Unexpected error loading DB credentials from environment: {e}", exc_info=True)
        db_connection_params = None # Clear on error
        raise

def initialize_config():
    """Initializes configurations that can be done once per cold start, like DB creds."""
    global db_connection_params
    logger.info("Initializing Lambda configuration...")
    if not db_connection_params:
        logger.info("db_connection_params not yet set. Calling _load_db_credentials_from_env().")
        try:
            _load_db_credentials_from_env()
            safe_params_to_log = {k: (v if k != 'password' else '********') for k, v in (db_connection_params or {}).items()}
            logger.info(f"_load_db_credentials_from_env() completed. db_connection_params (password masked): {safe_params_to_log}")
        except ValueError as ve:
            logger.error(f"ValueError during _load_db_credentials_from_env: {ve}. db_connection_params remains None.")
            # db_connection_params will be None due to error handling in _load_db_credentials_from_env
            raise # Re-raise to be caught by lambda_handler
        except Exception as ex:
            logger.error(f"Unexpected exception during _load_db_credentials_from_env: {ex}. db_connection_params remains None.", exc_info=True)
            raise # Re-raise to be caught by lambda_handler
    else:
        logger.info("db_connection_params already set. Skipping load.")
    logger.info("Lambda configuration initialization finished.")

def get_image_processor():
    """Returns a singleton instance of ImageProcessor."""
    global _image_proc_instance_singleton
    if _image_proc_instance_singleton is None:
        logger.info("Initializing ImageProcessor instance.")
        _image_proc_instance_singleton = ImageProcessor()
    return _image_proc_instance_singleton

# Example: Make sure ImageProcessor's potential env vars are also listed if it uses them
# FONT_S3_CACHE_BUCKET = os.environ.get('FONT_S3_CACHE_BUCKET') # Used by ImageProcessor
# GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY') # Used by ImageProcessor 