import sqlite3
import json
from datetime import datetime, timezone
import logging
from cryptography.fernet import Fernet
import base64
import os

# Setup logging
logger = logging.getLogger(__name__)
DATABASE_FILE = 'bkpmgt.db'

# obtain this from dotenv
password = "deepdefend_authpass"

# cryptsetup
# Derive a key from the password (for demonstration; use a secure key derivation in production)
def derive_key(password):
    # Generate a key based on the password (you might want to use a proper key derivation function)
    return base64.urlsafe_b64encode(password.encode('utf-8').ljust(32)[:32])

key = derive_key(password)
cipher_suite = Fernet(key)

def encrypt_password(password):
    """Encrypt the password using the global password-derived key."""
    return cipher_suite.encrypt(password.encode('utf-8')).decode('utf-8')

def decrypt_password(encrypted_password):
    """Decrypt the password using the global password-derived key."""
    return cipher_suite.decrypt(encrypted_password.encode('utf-8')).decode('utf-8')

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

    # Encrypt the password if it exists in the params
    if 'password' in params:
        password = params['password']
        encrypted_password = encrypt_password(password)  # Encrypt the password
        params['password'] = encrypted_password  # Replace the original password with the encrypted version

    try:
        connection = sqlite3.connect(DATABASE_FILE)
        cursor = connection.cursor()

        # Check if the command already exists using the encrypted params
        cursor.execute(f'SELECT COUNT(*) FROM {table_name} WHERE params = ?', (json.dumps(params),))
        count = cursor.fetchone()[0]

        if count == 0:  # Only insert if no existing record
            # Prepare data for insertion
            cursor.execute(f'''
                INSERT INTO {table_name} (params, response, response_timestamp)
                VALUES (?, ?, ?)
            ''', (json.dumps(params), json.dumps(response), response_timestamp))

            connection.commit()
        else:
            logger.info(f"Command with params already exists in {table_name}, skipping insert.")
    except Exception as e:
        logger.error(f"Failed to save command to database: {e}")
    finally:
        connection.close()

# Initialize the database when the module is loaded
initialize_database()