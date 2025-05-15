import psycopg2
from psycopg2.extras import DictCursor
# from .config import db_connection_params # OLD WAY - problematic for reassigned globals
from . import config as lambda_config # NEW WAY: import the module itself
from image_processor.logger import get_logger # For its own logger

logger = get_logger(__name__) # Specific logger for db_utils

def get_db_connection():
    """Establishes and returns a new database connection using pre-fetched params."""
    # print(f"[DEBUG_PRINT_V2] get_db_connection: lambda_config.db_connection_params are: {lambda_config.db_connection_params}") # DEBUG PRINT MODIFIED - Removed
    if not lambda_config.db_connection_params: # Access through the imported module
        logger.error("DB connection parameters not loaded. Call initialize_config from config module first or ensure it ran.")
        raise ConnectionError("Database parameters not initialized.")
    try:
        conn = psycopg2.connect(**lambda_config.db_connection_params) # Use the module-accessed params
        logger.info(f"Successfully connected to database {lambda_config.db_connection_params['dbname']} on {lambda_config.db_connection_params['host']}.")
        return conn
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL database: {e}", exc_info=True)
        raise

def execute_query(conn, query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """Executes a SQL query and returns results if any."""
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(query, params)
        if commit:
            conn.commit()
            return cur.rowcount # Return rowcount for commits
        if fetch_one:
            return cur.fetchone()
        if fetch_all:
            return cur.fetchall()
        return None 