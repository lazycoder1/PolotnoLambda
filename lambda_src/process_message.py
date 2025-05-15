import json
import copy # For deep copying template_json
from datetime import datetime, timezone # For timestamps
import uuid # Added for UUID generation

from .config import SQS_QUEUE_URL, sqs_client # For sending 'generate' messages
from .db_utils import execute_query
from .auth_utils import validate_auth0_token
from image_processor.logger import get_logger

logger = get_logger(__name__)

# Define a fixed namespace UUID for generating UUIDv5. 
# This can be any valid UUID. Generate one (e.g., online) and keep it constant.
NAMESPACE_UUID = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8') # Example, replace with your own if desired

def _fetch_data_for_processing(user_sub, user_template_id, db_conn):
    """Fetches all necessary data from the database for the 'process' workflow."""
    logger.info(f"Fetching user_template for user_sub: {user_sub}, user_template_id: {user_template_id}")
    template_query = "SELECT template_json, user_sub FROM facebook_test.user_templates WHERE user_sub = %s AND id = %s"
    template_row = execute_query(db_conn, template_query, (user_sub, user_template_id), fetch_one=True)
    if not template_row or not template_row['template_json']:
        logger.error(f"User template not found or template_json is empty for user_sub: {user_sub}, id: {user_template_id}")
        raise ValueError("User template not found or invalid.")
    base_template_json_str = template_row['template_json']
    
    # Ensure base_template_json is a dictionary
    if isinstance(base_template_json_str, str):
        try:
            base_template_json = json.loads(base_template_json_str)
            logger.info("Successfully parsed base_template_json string into a dictionary.")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse template_json string from DB for user_template_id {user_template_id}: {e}", exc_info=True)
            raise ValueError(f"Invalid JSON format in user_templates.template_json: {e}")
    elif isinstance(base_template_json_str, dict):
        base_template_json = base_template_json_str # It's already a dict
    else:
        logger.error(f"template_json from DB is neither a string nor a dict for user_template_id {user_template_id}. Type: {type(base_template_json_str)}")
        raise ValueError("Invalid data type for template_json from database.")

    logger.info("Successfully fetched base_template_json.")

    logger.info("Fetching field mapping definitions from facebook_test.fields")
    fields_mapping_query = "SELECT label_name, product_map, type FROM facebook_test.fields"
    fields_mapping = execute_query(db_conn, fields_mapping_query, fetch_all=True)
    if not fields_mapping:
        logger.warning("No field mappings found in facebook_test.fields. Dynamic replacement might not occur.")
        fields_mapping = []
    logger.info(f"Fetched {len(fields_mapping)} field mapping definitions.")
    
    logger.info(f"Fetching products for user_sub: {user_sub}")
    products_query = "SELECT * FROM facebook_test.products WHERE user_sub = %s" 
    products = execute_query(db_conn, products_query, (user_sub,), fetch_all=True)
    if not products:
        logger.info(f"No products found for user_sub: {user_sub}. No images will be generated.")
    logger.info(f"Fetched {len(products)} products for user_sub: {user_sub}")

    return base_template_json, fields_mapping, products

def _transform_single_template(template_to_transform, product_row, fields_mapping):
    """Transforms a single template JSON based on a product row and field mappings."""
    for page in template_to_transform.get("pages", []):
        for child_element in page.get("children", []):
            variable_name = child_element.get("custom", {}).get("variable")
            if not variable_name:
                continue

            field_def = next((f for f in fields_mapping if f['label_name'] == variable_name), None)
            if not field_def or not field_def['product_map']:
                continue

            product_column_name = field_def['product_map']
            if product_column_name not in product_row or product_row[product_column_name] is None:
                logger.warning(f"Product column '{product_column_name}' (mapped from '{variable_name}') not found in product ID '{product_row.get('id')}' or is null. Skipping modification for this child.")
                continue
            
            new_value = product_row[product_column_name]

            element_type = child_element.get("type")
            if element_type == "text":
                child_element["text"] = str(new_value)
            elif element_type == "image":
                if isinstance(new_value, str) and new_value.strip(): # Check if it's a non-empty string
                    if not (new_value.startswith('http://') or new_value.startswith('https://')):
                        logger.warning(f"Image src value for product ID '{product_row.get('id')}', variable '{variable_name}' does not look like a valid URL (missing http/https scheme): '{new_value}'. Skipping update for this image src.")
                    else:
                        child_element["src"] = new_value # Keep str() just in case, though it should be a string by now
                else:
                    logger.warning(f"Image src value for product ID '{product_row.get('id')}', variable '{variable_name}' is empty or not a string: '{new_value}'. Skipping update for this image src.")
    return template_to_transform

def _generate_product_specific_items(base_template_json, products, fields_mapping):
    """Generates a list of product-specific template JSONs."""
    generated_items = []
    if not products:
        return generated_items

    for product_row in products:
        logger.info(f"Preparing template for product ID: {product_row.get('id', 'N/A')}, Title: {product_row.get('title', 'N/A')}")
        new_template_json = copy.deepcopy(base_template_json)
        transformed_template = _transform_single_template(new_template_json, product_row, fields_mapping)
        generated_items.append({
            "json_data": transformed_template,
            "product_id": product_row.get('id')
        })
    logger.info(f"Generated {len(generated_items)} product-specific template items.")
    return generated_items

def _store_and_enqueue_generated_items(items_to_store, outfeed_id, user_template_id, user_sub, db_conn):
    """Stores generated items in DB using deterministic UUIDs and UPSERT, then enqueues them."""
    if not items_to_store:
        logger.info("No items were provided to store and enqueue.")
        return 0

    generated_feed_ids_to_enqueue = []
    try:
        for item in items_to_store:
            current_time = datetime.now(timezone.utc)
            product_id = item.get('product_id')

            if not product_id:
                logger.error(f"Item is missing product_id. Cannot generate deterministic UUID. Item data: {item.get('json_data', {}).get('name', 'N/A')}")
                continue

            # Construct the name for UUIDv5 generation
            # Ensure all parts are strings and handle potential None values for product_id
            name_for_uuid = f"{user_sub}-{user_template_id}-{outfeed_id}-{str(product_id)}"
            
            # Generate UUIDv5
            deterministic_feed_id = str(uuid.uuid5(NAMESPACE_UUID, name_for_uuid))
            
            logger.info(f"Generated deterministic UUID {deterministic_feed_id} for product {product_id}")

            # UPSERT: Insert or Update if conflict on 'id'
            # Ensure 'id' column is the primary key or has a unique constraint in 'generated_feeds'
            upsert_query = """
            INSERT INTO facebook_test.generated_feeds 
            (id, generated_json, outfeed_id, user_template_id, user_sub, status, error_message, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                generated_json = EXCLUDED.generated_json,
                outfeed_id = EXCLUDED.outfeed_id,
                user_template_id = EXCLUDED.user_template_id,
                user_sub = EXCLUDED.user_sub,
                status = EXCLUDED.status,
                error_message = NULL, -- Reset error message on update/overwrite
                generated_img_url = NULL, -- Reset image URL on update/overwrite
                updated_at = EXCLUDED.updated_at
            RETURNING id;
            """
            
            generated_json_str = json.dumps(item["json_data"])
            
            params = (
                deterministic_feed_id, 
                generated_json_str, 
                outfeed_id, 
                user_template_id, 
                user_sub, 
                'PROCESSED', # Initial status
                None, # error_message, initially null
                current_time, 
                current_time
            )
            
            generated_feed_row = execute_query(
                db_conn, 
                upsert_query, 
                params,
                fetch_one=True 
            )

            if generated_feed_row and generated_feed_row['id']:
                generated_feed_ids_to_enqueue.append(generated_feed_row['id'])
            else:
                logger.error(f"Failed to UPSERT generated_feed for product {product_id} (UUID: {deterministic_feed_id}) or retrieve ID. Skipping SQS message.")
        
        if generated_feed_ids_to_enqueue:
            db_conn.commit()
            logger.info(f"Committed {len(generated_feed_ids_to_enqueue)} new rows to generated_feeds.")

            for feed_id in generated_feed_ids_to_enqueue:
                sqs_message_body = {"type": "generate", "data": {"generated_feed_id": feed_id}}
                sqs_client.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(sqs_message_body))
                logger.info(f"Sent 'generate' message to SQS for generated_feed_id: {feed_id}")
            return len(generated_feed_ids_to_enqueue)
        else:
            logger.info("No feed IDs generated from items, nothing to commit or enqueue.")
            db_conn.rollback() # Should not happen if items_to_store had content and inserts were attempted
            return 0

    except Exception as e:
        logger.error(f"Error during DB inserts or SQS enqueueing: {e}", exc_info=True)
        db_conn.rollback()
        raise

def handle_process_workflow(message_data, db_conn):
    """Handles the 'process' message type workflow."""
    logger.info(f"Starting 'process' workflow for data: {message_data}")
    access_token = message_data.get('access_token')
    user_template_id = message_data.get('user_template_id')
    outfeed_id = message_data.get('outfeed_id')

    if not all([access_token, user_template_id, outfeed_id]):
        logger.error("'process' message missing required data (access_token, user_template_id, or outfeed_id).")
        raise ValueError("Incomplete data for 'process' message type.")

    try:
        user_sub = validate_auth0_token(access_token)
        if not user_sub:
            # validate_token_and_get_sub already logs and raises AuthError
            return # Should not be reached if AuthError is raised

        base_template_json, fields_mapping, products = _fetch_data_for_processing(user_sub, user_template_id, db_conn)
        
        # If no products, _generate_product_specific_items will return empty list, 
        # then _store_and_enqueue_generated_items will do nothing and return 0.
        # This is fine, it means the process for the outfeed_id completed, but generated 0 items.
        generated_items = _generate_product_specific_items(base_template_json, products, fields_mapping)
        
        enqueued_count = _store_and_enqueue_generated_items(generated_items, outfeed_id, user_template_id, user_sub, db_conn)
        # _store_and_enqueue_generated_items handles its own commit or rollback.
        # If it raises an exception, it will be caught by the generic except block below.

        logger.info(f"'process' workflow completed for user_template_id: {user_template_id}, outfeed_id: {outfeed_id}. Enqueued {enqueued_count} items.")
        return outfeed_id # Return the outfeed_id indicating this specific outfeed_id was processed.

    except AuthError as auth_err: # AuthError is already an Exception subclass
        logger.error(f"Authentication error in 'process' workflow: {auth_err}", exc_info=True)
        # No rollback here as AuthError happens before DB operations usually or should be idempotent
        raise # Re-raise to be caught by main.py
    except ValueError as val_err:
        logger.error(f"Value error in 'process' workflow for outfeed_id {outfeed_id}: {val_err}", exc_info=True)
        # No explicit rollback needed here if DB operations are structured well or if error is before writes
        raise # Re-raise
    except Exception as e:
        logger.error(f"Generic error in 'process' workflow for outfeed_id {outfeed_id}: {e}", exc_info=True)
        try:
            db_conn.rollback()
            logger.info(f"Database transaction rolled back for outfeed_id {outfeed_id} due to error.")
        except Exception as rb_err:
            logger.error(f"Failed to rollback DB transaction for outfeed_id {outfeed_id}: {rb_err}", exc_info=True)
        raise # Re-raise e to be caught by main.py 