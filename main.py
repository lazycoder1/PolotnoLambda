import json
import os # For local testing environment variable setup
from image_processor.logger import get_logger

# Import functionalities from the new lambda_src package
from lambda_src.config import initialize_config
from lambda_src.db_utils import get_db_connection, execute_query # Added execute_query for direct use if needed
from lambda_src.process_message import handle_process_workflow
from lambda_src.generate_message import handle_generate_workflow
from lambda_src.outfeed_status import get_status_for_outfeed # Import for getting outfeed stats

logger = get_logger(__name__) # Logger for main.py specific messages

# --- SQS Message Processing Logic ---

def _route_message_type(message_type, message_data, db_conn):
    """Routes message to the appropriate handler based on type. Returns outfeed_id if applicable."""
    if message_type == 'process':
        return handle_process_workflow(message_data, db_conn) # Returns outfeed_id on success
    elif message_type == 'generate':
        handle_generate_workflow(message_data, db_conn) # Does not return outfeed_id
        return None
    else:
        logger.warning(f"Unknown SQS message type: '{message_type}'. Skipping.")
        return None

def _process_sqs_record(record, db_conn_shared):
    """Processes a single SQS record. Returns outfeed_id if a 'process' message was successful."""
    logger.info(f"Processing SQS record with MessageId: {record.get('messageId')}")
    # db_conn is now passed in and managed by lambda_handler for the batch
    processed_outfeed_id_for_stats = None
    try:
        message_body_str = record.get('body')
        if not message_body_str:
            logger.warning("SQS record missing 'body'. Skipping.")
            return None # Successfully "processed" this malformed record by skipping
        
        message = json.loads(message_body_str)
        message_type = message.get('type')
        message_data = message.get('data', {})
        
        if isinstance(message_data, str):
            try:
                logger.info("message_data was a string, attempting to parse as JSON.")
                message_data = json.loads(message_data)
            except json.JSONDecodeError as json_err:
                logger.error(f"Failed to parse message_data string as JSON: {json_err}. Original string: {message_data}", exc_info=True)
                raise ValueError(f"message_data could not be parsed into a dictionary: {json_err}")

        logger.info(f"SQS Message Type: {message_type}")

        # Route and capture outfeed_id if returned (only for successful 'process' type)
        processed_outfeed_id_for_stats = _route_message_type(message_type, message_data, db_conn_shared)
        
        return processed_outfeed_id_for_stats

    except Exception as e:
        logger.error(f"Failed to process SQS message ID {record.get('messageId', 'N/A')} in _process_sqs_record: {e}", exc_info=True)
        # Rollback is handled by the main lambda_handler if an error propagates from here
        raise # Re-raise to be caught by lambda_handler, which handles rollback for the batch

# --- Main Lambda Handler ---
def lambda_handler(event, context):
    logger.info(f"Received SQS event with {len(event.get('Records', []))} records.")
    
    try:
        initialize_config() 
    except Exception as e:
        logger.critical(f"Lambda initialization failed (e.g., DB credentials): {e}. Cannot process event.", exc_info=True)
        return {'statusCode': 500, 'body': f'Lambda configuration error: {e}'}

    successfully_processed_outfeed_ids = set() # Use a set to store unique outfeed_ids
    batch_had_errors = False
    db_conn_batch = None

    try:
        db_conn_batch = get_db_connection() # Get one connection for the whole batch

        for record in event.get('Records', []):
            try:
                outfeed_id = _process_sqs_record(record, db_conn_batch)
                if outfeed_id: # This means a 'process' message for this outfeed_id was successful
                    successfully_processed_outfeed_ids.add(outfeed_id)
            except Exception as e:
                batch_had_errors = True
                # Error already logged by _process_sqs_record. 
                # This error will propagate out, causing the batch to fail SQS-wise.
                # We log it here again just for context of the batch handler.
                logger.error(f"Error during processing of SQS MessageId: {record.get('messageId')} within batch. Error: {e}", exc_info=True)
                # No need to raise here immediately, let loop continue if other messages can be tried,
                # but the overall batch will be marked as failed if any single message errors out and SQS retries.
                # For SQS, if any message in a batch fails and its exception propagates out of lambda_handler, 
                # the *entire batch* is returned to the queue for redrive/DLQ.
                # So, we MUST re-raise if we want SQS to handle it properly.
                raise # Re-raise to ensure SQS handles the message failure for this record.

        # If we reach here and batch_had_errors is True, it means an error was caught and re-raised.
        # If batch_had_errors is False, all messages in the batch were processed by _process_sqs_record without raising.

        # Fetch stats only if there were no errors during batch processing and we have outfeed_ids
        outfeed_statuses = []
        if not batch_had_errors and successfully_processed_outfeed_ids:
            logger.info(f"Fetching stats for successfully processed outfeed IDs: {successfully_processed_outfeed_ids}")
            for outfeed_id_stat in successfully_processed_outfeed_ids:
                try:
                    status = get_status_for_outfeed(db_conn_batch, outfeed_id_stat)
                    if status:
                        outfeed_statuses.append(status)
                    else:
                        logger.warning(f"No status found for outfeed_id: {outfeed_id_stat} during final status check.")
                        outfeed_statuses.append({
                            "outfeed_id": outfeed_id_stat,
                            "message": "No records found for this outfeed_id after processing."
                        })
                except Exception as stat_err:
                    logger.error(f"Failed to get status for outfeed_id {outfeed_id_stat}: {stat_err}", exc_info=True)
                    outfeed_statuses.append({"outfeed_id": outfeed_id_stat, "error": f"Failed to retrieve status: {stat_err}"})
            
            # Commit any transactions explicitly if all records processed successfully and stats fetched
            db_conn_batch.commit() 
            logger.info("Batch processing successful, final commit done.")
            response_body = {
                'message': 'SQS event processed successfully.',
                'processed_outfeed_stats': outfeed_statuses
            }
        elif not batch_had_errors:
            # Batch processed successfully, but no 'process' messages yielded outfeed_ids, or no records.
            db_conn_batch.commit() # Commit any successful work from (e.g.) 'generate' messages
            logger.info("Batch processing successful (no specific outfeed stats to report or no records), final commit done.")
            response_body = {'message': 'SQS event processed successfully. No new outfeed process stats to report from this batch.'}
        else:
            # This part should ideally not be reached if errors are re-raised correctly causing SQS redrive.
            # However, as a fallback defensive measure:
            logger.warning("Batch processing completed but with errors in some records. Rollback attempted.")
            db_conn_batch.rollback()
            # This response won't be seen if SQS retries the batch due to an earlier re-raised exception.
            response_body = {'message': 'SQS event processed with errors in some records. Check logs.'}
            # The actual failure for SQS is determined by a re-raised exception. 
            # If no exception is raised from here, SQS considers the batch successful despite this message.
            # This 'else' block for batch_had_errors is problematic if an error has already been raised.
            # The raise e within the loop ensures SQS handles failures. So, this block might be dead code
            # or indicate a logic flaw if reached without an exception having been propagated.
            # For now, let's assume the raise e in the loop is the primary failure mechanism for SQS.
            # So, if we get here with batch_had_errors=True, it means an error was raised and the lambda will exit non-200.
            # The code below this 'if/elif/else' for response_body might not execute if an error was raised.

        return {
            'statusCode': 200,
            'body': json.dumps(response_body)
        }

    except Exception as batch_level_exception:
        # This catches errors from get_db_connection() or if an error from _process_sqs_record was re-raised.
        logger.error(f"Error at batch level in lambda_handler: {batch_level_exception}", exc_info=True)
        if db_conn_batch:
            try:
                db_conn_batch.rollback()
                logger.info("Database transaction rolled back due to batch-level error.")
            except Exception as rb_err:
                logger.error(f"Failed to rollback DB transaction at batch level: {rb_err}", exc_info=True)
        raise batch_level_exception # Re-raise for SQS to handle (DLQ, retry)
    finally:
        if db_conn_batch:
            db_conn_batch.close()
            logger.info("Database connection closed at end of lambda_handler.")

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