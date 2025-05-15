import json
from .config import initialize_config
from .db_utils import execute_query, get_db_connection
from image_processor.logger import get_logger # Assuming shared logger config

logger = get_logger(__name__)

def get_status_for_outfeed(db_conn, outfeed_id):
    """Fetches generation status for a specific outfeed_id."""
    sql = """
    SELECT
        outfeed_id,
        COUNT(*) AS total_images,
        COUNT(CASE WHEN status = 'GENERATED' THEN 1 END) AS generated_count,
        COUNT(CASE WHEN status = 'GENERATION_FAIL' THEN 1 END) AS failed_count,
        COUNT(CASE WHEN status IN ('PROCESSED', 'GENERATING') THEN 1 END) AS processing_count
    FROM
        facebook_test.generated_feeds
    WHERE
        outfeed_id = %s
    GROUP BY
        outfeed_id;
    """
    logger.info(f"Fetching status for outfeed_id: {outfeed_id}")
    result = execute_query(db_conn, sql, (outfeed_id,), fetch_one=True)
    if result:
        # Convert Decimal counts to int for JSON serialization if necessary
        return {
            "outfeed_id": str(result["outfeed_id"]), # Ensure UUID is string
            "total_images": int(result["total_images"]),
            "generated_count": int(result["generated_count"]),
            "failed_count": int(result["failed_count"]),
            "processing_count": int(result["processing_count"])
        }
    return None

def lambda_handler(event, context):
    logger.info(f"Received event: {event}")
    initialize_config() # Ensure all configs like DB creds are loaded
    
    db_conn = None
    try:
        db_conn = get_db_connection()
        
        outfeed_id = None
        if event.get('pathParameters') and event['pathParameters'].get('outfeed_id'):
            outfeed_id = event['pathParameters'].get('outfeed_id')
        elif event.get('queryStringParameters') and event['queryStringParameters'].get('outfeed_id'):
            outfeed_id = event['queryStringParameters'].get('outfeed_id')

        if not outfeed_id:
            logger.warning("Outfeed ID not provided in pathParameters or queryStringParameters.")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Outfeed ID is required.'}),
                'headers': {'Content-Type': 'application/json'}
            }

        logger.info(f"Querying for specific outfeed_id: {outfeed_id}")
        data = get_status_for_outfeed(db_conn, outfeed_id)
        
        if data:
            response_data = data
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Outfeed ID not found or no records exist.'}),
                'headers': {'Content-Type': 'application/json'}
            }

        return {
            'statusCode': 200,
            'body': json.dumps(response_data),
            'headers': {'Content-Type': 'application/json'}
        }

    except Exception as e:
        logger.error(f"Error in outfeed_status_lambda: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)}),
            'headers': {'Content-Type': 'application/json'}
        }
    finally:
        if db_conn:
            db_conn.close()
            logger.info("Database connection closed.")

# For local testing:
# if __name__ == '__main__':
#     # Mock event for specific outfeed
#     # Make sure to replace 'your-actual-outfeed-uuid-from-db' with a real UUID from your DB
#     event_specific = {
#         'pathParameters': {'outfeed_id': 'your-actual-outfeed-uuid-from-db'}
#         # Or for query string testing:
#         # 'queryStringParameters': {'outfeed_id': 'your-actual-outfeed-uuid-from-db'}
#     }
#     print(lambda_handler(event_specific, None))
#
#     # Mock event for missing outfeed_id
#     event_missing_id = {}
#     print("\nTesting missing outfeed_id:")
#     print(lambda_handler(event_missing_id, None)) 