import json
import io # For BytesIO
from datetime import datetime, timezone # For timestamps

from .config import S3_IMAGE_OUTPUT_BUCKET, s3_client, get_image_processor
from .db_utils import execute_query, get_db_connection # get_db_connection for error recovery
from image_processor.logger import get_logger

logger = get_logger(__name__)

class PartialImageGenerationError(ValueError):
    """Custom error for when image generation completes but has element-level errors."""
    pass

def _prepare_feed_for_generation(generated_feed_id, db_conn):
    """Fetches generated_json if status is PROCESSED, then updates status to GENERATING."""
    logger.info(f"Preparing feed for generation: {generated_feed_id}")
    select_query = "SELECT id, generated_json, user_sub, outfeed_id FROM facebook_test.generated_feeds WHERE id = %s AND status = 'PROCESSED';"
    feed_to_generate = execute_query(db_conn, select_query, (generated_feed_id,), fetch_one=True)

    if not feed_to_generate or not feed_to_generate['generated_json']:
        current_status_row = execute_query(db_conn, "SELECT status FROM facebook_test.generated_feeds WHERE id = %s", (generated_feed_id,), fetch_one=True)
        current_status = current_status_row['status'] if current_status_row else "NOT_FOUND"
        logger.warning(f"Generated feed id: {generated_feed_id} not found or not in 'PROCESSED' state. Current state: {current_status}. Skipping generation.")
        return None
        
    update_status_query = "UPDATE facebook_test.generated_feeds SET status = 'GENERATING', updated_at = %s WHERE id = %s;"
    execute_query(db_conn, update_status_query, (datetime.now(timezone.utc), generated_feed_id), commit=True)
    logger.info(f"Status for generated_feed_id {generated_feed_id} updated to GENERATING.")
    
    return {
        "json_data_str": feed_to_generate['generated_json'],
        "user_sub": feed_to_generate.get('user_sub', 'unknown_user'),
        "outfeed_id": feed_to_generate.get('outfeed_id', 'unknown_outfeed')
    }

def _generate_and_store_image(generated_json_data, generated_feed_id, user_sub, outfeed_id):
    """Generates image using ImageProcessor and uploads to S3. Returns S3 URL or raises error."""
    image_proc = get_image_processor() # Get singleton instance
    
    logger.info(f"Starting image processing for generated_feed_id: {generated_feed_id}...")
    
    parsed_json_data = None
    if isinstance(generated_json_data, str):
        try:
            parsed_json_data = json.loads(generated_json_data)
        except json.JSONDecodeError as je:
            logger.error(f"Invalid JSON string for generated_feed_id {generated_feed_id}: {je}")
            raise ValueError(f"Invalid JSON string for image generation: {je}") from je
    elif isinstance(generated_json_data, dict):
        parsed_json_data = generated_json_data # Already a dict
    else:
        logger.error(f"generated_json_data for {generated_feed_id} is neither a string nor a dict: {type(generated_json_data)}")
        raise TypeError(f"JSON data for image generation must be a string or a dictionary, got {type(generated_json_data)}")

    if parsed_json_data is None: # Should not happen if logic above is correct, but as a safeguard
        logger.error(f"parsed_json_data is None for {generated_feed_id} after type checking and parsing attempt.")
        raise ValueError(f"Failed to obtain valid JSON data for image generation for {generated_feed_id}")

    result_image, processing_errors = image_proc.combine_images(parsed_json_data) 

    if result_image is None: # Critical failure in combine_images itself
        error_summary = f"Critical error during image processing: {processing_errors[0] if processing_errors else 'Unknown image processing error'}"
        logger.error(error_summary)
        raise ValueError(error_summary) # Or a more specific error type

    if processing_errors: # Non-critical, but element-level errors occurred
        error_summary = f"Image generation for {generated_feed_id} had {len(processing_errors)} element errors: {'; '.join(processing_errors)[:500]}" # Limit summary length
        logger.warning(error_summary) # Log as warning, but will be raised as an error to mark DB
        raise PartialImageGenerationError(error_summary) # Custom error to signify this state

    logger.info("Image processing complete with no element errors.")
    
    buffer = io.BytesIO()
    result_image.save(buffer, format='PNG')
    buffer.seek(0)
    
    output_key = f"processed_images/{user_sub}/{outfeed_id}/{generated_feed_id}.png"
    
    logger.info(f"Uploading PNG to s3://{S3_IMAGE_OUTPUT_BUCKET}/{output_key}")
    s3_client.put_object(
        Bucket=S3_IMAGE_OUTPUT_BUCKET, 
        Key=output_key, 
        Body=buffer, 
        ContentType='image/png'
    )
    s3_image_url = f"https://{S3_IMAGE_OUTPUT_BUCKET}.s3.amazonaws.com/{output_key}" # Standard HTTPS S3 URL
    logger.info(f"Successfully uploaded image to S3: {s3_image_url}. Ensure bucket policy allows public read.")
    return s3_image_url

def _update_final_generation_status(generated_feed_id, db_conn, s3_image_url=None, error=None):
    """Updates the generated_feeds table to GENERATED or GENERATION_FAIL."""
    current_time = datetime.now(timezone.utc)
    if error:
        logger.error(f"Updating status to GENERATION_FAIL for {generated_feed_id} due to: {error}")
        error_message_str = str(error)[:1000] # Truncate for DB
        update_query = "UPDATE facebook_test.generated_feeds SET status = 'GENERATION_FAIL', error_message = %s, updated_at = %s WHERE id = %s;"
        params = (error_message_str, current_time, generated_feed_id)
    elif s3_image_url:
        logger.info(f"Updating status to GENERATED for {generated_feed_id} with URL: {s3_image_url}")
        update_query = "UPDATE facebook_test.generated_feeds SET status = 'GENERATED', generated_img_url = %s, updated_at = %s WHERE id = %s;"
        params = (s3_image_url, current_time, generated_feed_id)
    else:
        logger.error(f"_update_final_generation_status called without S3 URL or error for {generated_feed_id}")
        return

    try:
        execute_query(db_conn, update_query, params, commit=True)
        logger.info(f"Final status for {generated_feed_id} updated successfully.")
    except Exception as db_err:
        logger.error(f"Failed to update final status for {generated_feed_id}: {db_err}", exc_info=True)
        raise

def handle_generate_workflow(message_data, db_conn):
    """Handles the 'generate' message type workflow."""
    logger.info(f"Starting 'generate' workflow for data: {message_data}")
    generated_feed_id = message_data.get('generated_feed_id')

    if not generated_feed_id:
        logger.error("'generate' message missing 'generated_feed_id'.")
        raise ValueError("Incomplete data for 'generate' message type.")

    preparation_data = None
    s3_image_url = None
    try:
        preparation_data = _prepare_feed_for_generation(generated_feed_id, db_conn)
        if not preparation_data:
            return

        s3_image_url = _generate_and_store_image(
            preparation_data["json_data_str"],
            generated_feed_id, 
            preparation_data["user_sub"],
            preparation_data["outfeed_id"]
        )
        
        _update_final_generation_status(generated_feed_id, db_conn, s3_image_url=s3_image_url)
        logger.info(f"'generate' workflow completed successfully for {generated_feed_id}.")

    except Exception as e:
        logger.error(f"Error during 'generate' workflow for {generated_feed_id}: {e}", exc_info=True)
        try:
            # Ensure db_conn is usable for final status update, might have closed on prior DB error in helpers
            if hasattr(db_conn, 'closed') and db_conn.closed:
                logger.warning("DB connection was closed before final failure status update. Attempting to reopen.")
                db_conn = get_db_connection() # Attempt to get a fresh connection
            _update_final_generation_status(generated_feed_id, db_conn, error=e)
        except Exception as final_status_update_err:
            logger.error(f"Critical: Failed to even update status to GENERATION_FAIL for {generated_feed_id}. Primary error: {e}. Status update error: {final_status_update_err}", exc_info=True)
        raise e 