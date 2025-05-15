import json
import os # For local testing environment variable setup
from image_processor.logger import get_logger

# Import functionalities from the new lambda_src package
from lambda_src.config import initialize_config
from lambda_src.db_utils import get_db_connection
from lambda_src.process_message import handle_process_workflow
from lambda_src.generate_message import handle_generate_workflow

logger = get_logger(__name__) # Logger for main.py specific messages

# --- SQS Message Processing Logic ---

def _route_message_type(message_type, message_data, db_conn):
    """Routes message to the appropriate handler based on type."""
    if message_type == 'process':
        handle_process_workflow(message_data, db_conn) # Use imported handler
    elif message_type == 'generate':
        handle_generate_workflow(message_data, db_conn) # Use imported handler
    else:
        logger.warning(f"Unknown SQS message type: '{message_type}'. Skipping.")
        # This message will be considered successfully processed by default unless an error is raised.

def _process_sqs_record(record):
    """Processes a single SQS record."""
    logger.info(f"Processing SQS record with MessageId: {record.get('messageId')}")
    db_conn = None
    try:
        message_body_str = record.get('body')
        if not message_body_str:
            logger.warning("SQS record missing 'body'. Skipping.")
            return # Successfully "processed" this malformed record by skipping
        
        message = json.loads(message_body_str)
        message_type = message.get('type')
        message_data = message.get('data', {})
        
        # Check if message_data is a string (e.g., double-encoded JSON)
        if isinstance(message_data, str):
            try:
                logger.info("message_data was a string, attempting to parse as JSON.")
                message_data = json.loads(message_data)
            except json.JSONDecodeError as json_err:
                logger.error(f"Failed to parse message_data string as JSON: {json_err}. Original string: {message_data}", exc_info=True)
                # Depending on desired behavior, you might want to raise an error here or skip the record.
                # For now, we'll let it proceed, and it will likely fail in the handler if message_data is not a dict.
                # Or, more robustly, ensure it's a dict or raise:
                raise ValueError(f"message_data could not be parsed into a dictionary: {json_err}")

        logger.info(f"SQS Message Type: {message_type}")

        db_conn = get_db_connection() # Use imported function from db_utils
        _route_message_type(message_type, message_data, db_conn)
        # If no exception, processing is successful for this message.
        # Commit/rollback is handled within the workflow functions in their respective modules.

    except Exception as e:
        # Errors from _route_message_type (and underlying workflows) will be caught here.
        logger.error(f"Failed to process SQS message ID {record.get('messageId', 'N/A')}: {e}", exc_info=True)
        if db_conn:
            try:
                db_conn.rollback() # Ensure rollback on any unhandled error from workflows
                logger.info("Database transaction rolled back due to error in record processing.")
            except Exception as rb_err:
                logger.error(f"Failed to rollback DB transaction: {rb_err}", exc_info=True)
        raise # Re-raise to signal SQS that this message failed processing (caught by lambda_handler)
    finally:
        if db_conn:
            db_conn.close()
            logger.info("Database connection closed for SQS record processing cycle.")

# --- Main Lambda Handler ---
def lambda_handler(event, context):
    logger.info(f"Received SQS event with {len(event.get('Records', []))} records.")
    
    try:
        initialize_config() # Initialize configuration (e.g., DB creds) from lambda_src.config
    except Exception as e:
        logger.critical(f"Lambda initialization failed (e.g., DB credentials): {e}. Cannot process event.", exc_info=True)
        # This is a fatal error for this invocation. 
        # SQS messages (if any in the event) will be returned to the queue and retried.
        return {'statusCode': 500, 'body': f'Lambda configuration error: {e}'}

    for record in event.get('Records', []):
        try:
            _process_sqs_record(record)
            # If _process_sqs_record completes without raising an exception,
            # Lambda considers this message successfully processed from its perspective.
            # SQS will delete it if the overall lambda_handler invocation succeeds for this message.
        except Exception as e:
            print(f"[DEBUG_PRINT] lambda_handler: Exception from _process_sqs_record for {record.get('messageId')}: {str(e)}") # DEBUG PRINT
            # Error already logged by _process_sqs_record.
            # This exception must propagate out of lambda_handler for SQS to correctly handle the failed message (retry/DLQ).
            logger.error(f"Error during processing of SQS MessageId: {record.get('messageId')}. Re-raising to Lambda runtime.", exc_info=True)
            raise e # Re-raise the exception. If any record in a batch fails, the whole batch is typically retried by SQS.

    # This return is reached only if all records in the batch are processed without raising an unhandled exception.
    print("[DEBUG_PRINT] lambda_handler: Exiting function successfully.") # DEBUG PRINT
    return {
        'statusCode': 200, 
        'body': json.dumps('SQS event processed (see logs for individual message status; all processed messages in this batch were successful).')
    }

# Local testing placeholder
if __name__ == "__main__":
    # This block is for local testing convenience.
    # Ensure all required environment variables (defined in lambda_src/config.py) are set in your local environment.
    # For example:
    # os.environ['SQS_QUEUE_URL'] = 'your_sqs_queue_url'
    # os.environ['DB_HOST'] = 'your_db_host'
    # os.environ['DB_PORT'] = '5432'
    # os.environ['DB_NAME'] = 'your_db_name'
    # os.environ['DB_USER'] = 'your_db_user'
    # os.environ['DB_PASSWORD'] = 'your_db_password'
    # os.environ['AUTH0_DOMAIN'] = 'your-auth0-domain.auth0.com'
    # os.environ['AUTH0_AUDIENCE'] = 'your-auth0-api-audience'
    # os.environ['S3_IMAGE_OUTPUT_BUCKET'] = 'your-s3-output-bucket'
    # etc.

    logger.info("Local testing: Simulating Lambda execution.")
    logger.info("Ensure required ENV VARS (DB_HOST, DB_USER, SQS_QUEUE_URL etc.) are set for submodules to pick up.")

    # Example "process" event for local testing
    sample_process_event = {
        "Records": [
            {
                "messageId": "local-test-process-message-id-1",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps({
                    "type": "process",
                    "data": {
                        "access_token": "dummy_access_token_for_local_test", 
                        "user_template_id": "some_uuid_template_local",
                        "outfeed_id": "some_uuid_outfeed_local"
                    }
                }),
                "attributes": {}, "messageAttributes": {}, "md5OfBody": "", "eventSource": "aws:sqs", "eventSourceARN": "", "awsRegion": "us-east-1"
            }
        ]
    }
    
    # Example "generate" event for local testing
    sample_generate_event = {
        "Records": [
            {
                "messageId": "local-test-generate-message-id-1",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps({
                    "type": "generate",
                    "data": {
                        "generated_feed_id": "dummy_generated_feed_id_for_local_test" 
                    }
                }),
                "attributes": {}, "messageAttributes": {}, "md5OfBody": "", "eventSource": "aws:sqs", "eventSourceARN": "", "awsRegion": "us-east-1"
            }
        ]
    }

    # --- To run local tests, uncomment one of the blocks below and ensure all ENV VARS are set ---
    # print("\nAttempting local test of 'process' workflow...")
    # try:
    #     # Initialize config first, as lambda_handler would do
    #     initialize_config()
    #     lambda_handler(sample_process_event, None)
    #     print("Local 'process' test completed. Check logs.")
    # except Exception as e_process:
    #     logger.error(f"Local test of 'process' workflow failed critically: {e_process}", exc_info=True)

    # print("\nAttempting local test of 'generate' workflow...")
    # try:
    #     # Initialize config first, as lambda_handler would do
    #     initialize_config()
    #     lambda_handler(sample_generate_event, None)
    #     print("Local 'generate' test completed. Check logs.")
    # except Exception as e_generate:
    #     logger.error(f"Local test of 'generate' workflow failed critically: {e_generate}", exc_info=True)
    
    pass # End of local testing block