import sqlite3
import json
from datetime import datetime, timezone
import logging

# Setup logging
logger = logging.getLogger(__name__)
DATABASE_FILE = 'command_history.db'

def initialize_database():
    """Initialize the database and create tables for each command type if they don't exist."""
    try:
        connection = sqlite3.connect(DATABASE_FILE)
        cursor = connection.cursor()

        # Create separate tables for each command type
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS local_repo_init (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                params TEXT NOT NULL,
                response TEXT NOT NULL,
                response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS local_repo_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                params TEXT NOT NULL,
                response TEXT NOT NULL,
                response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS local_repo_backup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                params TEXT NOT NULL,
                response TEXT NOT NULL,
                response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS local_repo_restore (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                params TEXT NOT NULL,
                response TEXT NOT NULL,
                response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS s3_repo_backup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                params TEXT NOT NULL,
                response TEXT NOT NULL,
                response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        connection.commit()
    except Exception as e:
        logger.error(f"Failed to initialize the database: {e}")
    finally:
        connection.close()

def save_command(command_type, params, response):
    """Save the command details to the appropriate table based on the command type."""
    response_timestamp = datetime.now(timezone.utc).isoformat()  # Get current timestamp in UTC
    table_name = command_type.replace(" ", "_").lower()  # Normalize table name

    try:
        connection = sqlite3.connect(DATABASE_FILE)
        cursor = connection.cursor()

        # Prepare data for insertion
        cursor.execute(f'''
            INSERT INTO {table_name} (params, response, response_timestamp)
            VALUES (?, ?, ?)
        ''', (json.dumps(params), json.dumps(response), response_timestamp))
        
        connection.commit()
    except Exception as e:
        logger.error(f"Failed to save command to database: {e}")
    finally:
        connection.close()

# Initialize the database when the module is loaded
initialize_database()