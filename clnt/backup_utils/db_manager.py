import asyncio
import aiosqlite
import json
from datetime import datetime, timezone
import logging
from cryptography.fernet import Fernet
import base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# Setup logging
logger = logging.getLogger(__name__)
DATABASE_FILE = 'bkpmgt.db'

# obtain this from dotenv
password = "deepdefend_authpass"

# cryptsetup
# Derive a key using a more secure approach (PBKDF2)
def derive_key(password):
    """Derive a secure key using PBKDF2HMAC."""
    salt = b'\x00' * 16  # In production, use a unique salt and store it securely.
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))

key = derive_key(password)
cipher_suite = Fernet(key)

def encrypt_field(input):
    """Encrypt the password using the global password-derived key."""
    return cipher_suite.encrypt(input.encode('utf-8')).decode('utf-8')

def decrypt_field(input):
    """Decrypt the password using the global password-derived key."""
    return cipher_suite.decrypt(input.encode('utf-8')).decode('utf-8')

def normalize_params(params):
    return json.dumps(params, sort_keys=True)

async def initialize_database():
    """Initialize the database and create tables for each command type if they don't exist."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as connection:
            cursor = await connection.cursor()

            # Create separate tables for each command type
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS init_local_repo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    params TEXT NOT NULL,
                    response TEXT NOT NULL,
                    response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS get_local_repo_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    params TEXT NOT NULL,
                    response TEXT NOT NULL,
                    response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS do_local_repo_backup (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    params TEXT NOT NULL,
                    response TEXT NOT NULL,
                    response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS do_local_repo_restore (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    params TEXT NOT NULL,
                    response TEXT NOT NULL,
                    response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS do_s3_repo_backup (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    params TEXT NOT NULL,
                    response TEXT NOT NULL,
                    response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS do_s3_repo_restore (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    params TEXT NOT NULL,
                    response TEXT NOT NULL,
                    response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create separate tables for each response type
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS response_local_repo_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    response TEXT NOT NULL,
                    response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS response_s3_repo_restore (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    response TEXT NOT NULL,
                    response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS response_local_repo_backup (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    response TEXT NOT NULL,
                    response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS response_local_repo_restore (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    response TEXT NOT NULL,
                    response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS response_s3_repo_backup (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    response TEXT NOT NULL,
                    response_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create the schedule ledger table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedule_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    params TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                )
            ''')

            await connection.commit()
    except Exception as e:
        logger.error(f"Failed to initialize the database: {e}")

async def save_command(command_type, params, response):
    """Save the command details to the appropriate table based on the command type."""
    response_timestamp = datetime.now(timezone.utc).isoformat()  # Get current timestamp in UTC
    table_name = command_type.replace(" ", "_").lower()  # Normalize table name

    # Encrypt the password if it exists in the params
    if 'password' in params:
        params['password'] = encrypt_field(params['password'])

    if command_type.startswith('do_s3_repo_'):
        params['aws_access_key_id'] = encrypt_field(params['aws_access_key_id'])
        params['aws_secret_access_key'] = encrypt_field(params['aws_secret_access_key'])

        if not params['aws_session_token'] == "":
            params['aws_session_token'] = encrypt_field(params['aws_session_token'])

    try:
        async with aiosqlite.connect(DATABASE_FILE) as connection:
            cursor = await connection.cursor()

            # Check if the command already exists using the encrypted params
            await cursor.execute(f'SELECT COUNT(*) FROM {table_name} WHERE params = ?', (normalize_params(params),))
            count = await cursor.fetchone()
            count = count[0] if count else 0

            if count == 0:  # Only insert if no existing record
                await cursor.execute(f'''
                    INSERT INTO {table_name} (params, response, response_timestamp)
                    VALUES (?, ?, ?)
                ''', (normalize_params(params), json.dumps(response), response_timestamp))

                await connection.commit()
            else:
                logger.info(f"Command with params already exists in {table_name}, skipping insert.")
    except Exception as e:
        logger.error(f"Failed to save command to database: {e}")

async def save_scheduled_task(params):
    """Save a scheduled task to the schedule ledger."""
    
    # Encrypt sensitive fields if they exist in the params
    if 'password' in params:
        params['password'] = encrypt_field(params['password'])

    if 'aws_access_key_id' in params:
        params['aws_access_key_id'] = encrypt_field(params['aws_access_key_id'])
    
    if 'aws_secret_access_key' in params:
        params['aws_secret_access_key'] = encrypt_field(params['aws_secret_access_key'])

    if 'aws_session_token' in params and params['aws_session_token'] != "":
        params['aws_session_token'] = encrypt_field(params['aws_session_token'])
        
    try:
        async with aiosqlite.connect(DATABASE_FILE) as connection:
            cursor = await connection.cursor()

            await cursor.execute('''
                INSERT INTO schedule_ledger (params, status)
                VALUES (?, ?)
            ''', (json.dumps(params), 'pending'))

            await connection.commit()
    except Exception as e:
        logger.error(f"Failed to save scheduled task: {e}")

async def update_schtask(response):
    response_timestamp = datetime.now(timezone.utc).isoformat()  # Get current timestamp in UTC
    task_type = response.get("type")
    table_name = task_type.replace(" ", "_").lower()  # Normalize table name

    try:
        async with aiosqlite.connect(DATABASE_FILE) as connection:
            cursor = await connection.cursor()

            # Check if the command already exists using the response
            await cursor.execute(f'SELECT COUNT(*) FROM {table_name} WHERE response = ?', (normalize_params(response),))
            count = await cursor.fetchone()
            count = count[0] if count else 0

            if count == 0:  # Only insert if no existing record
                await cursor.execute(f'''
                    INSERT INTO {table_name} (response, response_timestamp)
                    VALUES (?, ?)
                ''', (normalize_params(response), response_timestamp))

                await connection.commit()
            else:
                logger.info(f"response already exists in {table_name}, skipping insert.")
    except Exception as e:
        logger.error(f"Failed to save response to database: {e}")

# Initialize the database when the module is loaded
asyncio.run(initialize_database())