# backup_utils/handlers.py
import logging
import subprocess
import json
import re
import os
import boto3 # AWS SDK for Python
import botocore # for exception handling
from backup_utils.db_manager import save_command, update_schtask
from sys_utils.resource_helper import *
import uuid
import websockets

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

restic_path = get_restic_path()

async def handle_init_local_repo(params, websocket):
    """
    Initialize a local restic repository with a given password and log the output in JSON format when applicable.
    Also, send the initialization output to the server over WebSocket.
    """
    logger.info(f"Initializing Restic repository at: {params['repo_path']}")
    password = params.get('password')
    repo_path = params.get('repo_path')
    command_history = params.get('command_history', True)

    command = [restic_path, '-r', repo_path, 'init', '--json']

    try:
        # Start the command using subprocess and provide the password via stdin
        result = subprocess.run(command, input=f"{password}\n", text=True, capture_output=True)

        if result.returncode != 0:
            # Check for the specific error indicating the repo is already initialized
            if "config file already exists" in result.stderr:
                error_message = f"Repository at {repo_path} is already initialized. Need a different path!"
                logger.error(error_message)
                return

            # Handle other fatal errors
            if "Fatal" in result.stderr:
                error_message = result.stderr.strip()
                logger.error(error_message)
                return

            # General command failure
            error_message = f"Command failed with return code {result.returncode}: {result.stderr}"
            logger.error(error_message)
            return

        # Log the raw command output
        output = result.stdout.strip()
        logger.info(f"Command output:\n{output}")

        # Filter out the non-JSON part (e.g., "reading repository password from stdin")
        json_start = output.find('{')  # Find the start of the JSON object
        if json_start != -1:
            json_data = output[json_start:]  # Extract JSON part of the output
        else:
            logger.error("No JSON found in the command output.")
            return

        # Parse the JSON output
        try:
            init_response = json.loads(json_data)
            logger.info(f"Parsed initialization output: {init_response}")

            if command_history:
                # Save the command and its response to the database
                await save_command('init_local_repo', params, init_response)

            # Create a message to send to the server
            message_to_server = {
                "type": "response_init_local_repo",  # Define the message type for repo initialization
                "summary": init_response  # Send the parsed JSON output as the summary
            }

            # Send the message to the server over WebSocket
            await websocket.send(json.dumps(message_to_server, indent=2))
            logger.info(f"Repo initialization data sent to server for repo: {repo_path}")

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON output from restic.")
            return

    except subprocess.TimeoutExpired:
        logger.error("Timeout while initializing the repository.")
        return
    except Exception as e:
        logger.error(f"Failed to initialize repository: {e}")
        return

async def handle_get_local_repo_snapshots(params, websocket=None):
    """
    Handle 'get_local_repo_snapshots' message type with restic and send results to the server.
    """
    logger.info(f"Received task to list snapshots for repo: {params['repo_path']}")

    password = params.get('password')
    repo_path = params.get('repo_path')
    command_history = params.get('command_history', True)
    optype = params.get("type")

    if not password or not repo_path:
        logger.error("Password and repository path are required.")
        return  # No return, just log the error
    
    command = [restic_path, '-r', repo_path, 'snapshots', '--json']

    try:
        # Start the command using subprocess and provide the password via stdin
        result = subprocess.run(command, input=f"{password}\n", text=True, capture_output=True)

        if result.returncode != 0:
            logger.error(f"Command failed with return code {result.returncode}: {result.stderr}")
            return

        output = result.stdout

        # Log the raw command output
        logger.info(f"Command output:\n{output}")

        # Use regex to find the part of the output that contains valid JSON
        json_start = re.search(r'(\[|\{)', output)
        if json_start:
            json_data = output[json_start.start():]  # Extract JSON part of the output
            snapshots = json.loads(json_data)  # Parse the JSON output
            logger.info(f"Parsed snapshots: {snapshots}")

            if command_history:
                await save_command('get_local_repo_snapshots', params, snapshots)

            # Create a message to send to the server
            message_to_server = {
                "type": "response_local_repo_snapshots",
                # "systemUuid": system_uuid,  # Send system UUID; this is will be resolved by the server WS
                "repo_path": repo_path,
                "snapshots": snapshots,
            }

            if not optype.startswith("schedule_") and websocket.state == websockets.protocol.State.OPEN:
                # If websocket is available, send the response to the server via WebSocket
                await websocket.send(json.dumps(message_to_server, indent=2))
                logger.info("Response sent over WebSocket.")
            else:
                # WebSocket is may not be available, save the response to local database
                await update_schtask(message_to_server)
                logger.info("Response saved to local database due to lack of WebSocket connection.")

        else: # Future: create a message payload with failure output
            logger.error("No JSON found in the command output.")

    except subprocess.TimeoutExpired:
        logger.error("Timeout waiting for password prompt.")
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON output from restic.")
    except Exception as e:
        logger.error(f"Failed to execute command: {e}")

async def handle_do_local_repo_backup(params, websocket=None):

    task_uuid = str(uuid.uuid4())  # Generate a unique task UUID for this particular backup task

    logger.info(f"Received request to perform local repo backup for repo: {params['repo_path']}")

    repo_path = params.get('repo_path')
    password = params.get('password')
    paths = params.get('paths', [])  # Get the paths for backup
    exclude = params.get('exclude', [])  # Optional exclude filters
    custom_options = params.get('custom_options', [])  # Any additional options
    tags = params.get('tags', [])  # Optional tags
    command_history = params.get('command_history', True)
    optype = params.get("type")

    if not password or not repo_path:
        logger.error("Password and repository path are required.")
        return  # Log the error and return

    # Build the backup command
    command = [restic_path, '-r', repo_path, 'backup', '--json'] + paths

    # Append each exclusion separately
    for ex in exclude:
        command += ['--exclude', ex]
    
    if custom_options:
        command += custom_options
    
    if tags:
        command += ['--tag'] + tags
    
    logger.info(f"this is the command that would be executed {command}")

    try:
        # task status
        message_to_server = {
            "task_uuid": task_uuid, # non-persistent, move out to local DB later
            "type": "response_local_repo_backup",  # Define the message type for backup
            "repo_path": repo_path,
            "backup_output": "",
            "task_status": "processing",
        }

        # send first message
        if not optype.startswith("schedule_") and websocket.state == websockets.protocol.State.OPEN:
            await websocket.send(json.dumps(message_to_server, indent=2))
            logger.info("Response sent over WebSocket.")
        else:
            await update_schtask(message_to_server)
            logger.info("Response saved to local database due to lack of WebSocket connection (Possibly a Scheduled task)")

        # Start the command using subprocess and provide the password via stdin
        result = subprocess.run(command, input=f"{password}\n", text=True, capture_output=True)
        # try except to send failed message
        if result.returncode != 0:
            logger.error(f"Command failed with return code {result.returncode}: {result.stderr}")
            return

        output = result.stdout

        # Log the raw command output
        logger.info(f"Command output:\n{output}")

        # Split output into lines and filter for the summary message
        summary_message = None
        for line in output.splitlines():
            try:
                message = json.loads(line)
                if message.get("message_type") == "summary":
                    summary_message = message
                    break  # Stop after finding the first summary
            except json.JSONDecodeError:
                continue  # Skip non-JSON lines

        if summary_message:
            logger.info(f"Parsed backup summary output: {summary_message}")
            
            if command_history:
                await save_command('do_local_repo_backup', params, summary_message)

            # Create a message to send to the server
            message_to_server = {
                "task_uuid": task_uuid,
                "type": "response_local_repo_backup",  # Define the message type for backup
                "repo_path": repo_path,
                "backup_output": summary_message,
                "task_status": "completed",
            }

            if not optype.startswith("schedule_") and websocket.state == websockets.protocol.State.OPEN:
                # If websocket is available, send the response to the server via WebSocket
                await websocket.send(json.dumps(message_to_server, indent=2))
                logger.info("Response sent over WebSocket.")
            else:
                # WebSocket is may not be available, save the response to local database
                await update_schtask(message_to_server)
                logger.info("Response saved to local database due to lack of WebSocket connection.")

        else:
            logger.error("No JSON found in the command output.")

    except subprocess.TimeoutExpired:
        logger.error("Timeout while waiting for the backup command.")
    except Exception as e:
        logger.error(f"Failed to execute command: {e}")

async def handle_do_local_repo_restore(params, websocket=None):
    """
    Handle 'do_local_repo_restore' message type to restore files from a local Restic repository.
    """
    task_uuid = str(uuid.uuid4())  # Generate a unique task UUID for this particular restore task
    logger.info(f"Received request to perform local repo restore for repo: {params['repo_path']}")

    repo_path = params.get('repo_path')
    password = params.get('password')
    snapshot_id = params.get('snapshot_id', 'latest')  # Default to 'latest' if no snapshot_id is provided
    target_path = params.get('target_path', '.')  # Where to restore the files
    exclude = params.get('exclude', [])  # Optional exclude filters
    include = params.get('include', [])  # Optional include filters
    custom_options = params.get('custom_options', [])  # Any additional options
    command_history = params.get('command_history', True)
    optype = params.get("type")

    if not password or not repo_path or not snapshot_id:
        logger.error("Password, repository path, and snapshot ID are required.")
        return  # Log the error and return

    # Build the restore command
    command = [restic_path, '-r', repo_path, 'restore', snapshot_id, '--target', target_path, '--json']

    # Append each exclusion separately
    for ex in exclude:
        command += ['--exclude', ex]

    # Append each inclusion separately
    for inc in include:
        command += ['--include', inc]

    if custom_options:
        command += custom_options

    logger.info(f"Executing restore command: {command}")

    try:
        # task status
        message_to_server = {
            "task_uuid": task_uuid, # non-persistent, move out to local DB later
            "type": "response_local_repo_restore",  # Define the message type for restore
            "repo_path": repo_path,
            "restore_output": "",
            "task_status": "processing",
        }

        # send first message
        if not optype.startswith("schedule_") and websocket.state == websockets.protocol.State.OPEN:
            await websocket.send(json.dumps(message_to_server, indent=2))
            logger.info("Response sent over WebSocket.")
        else:
            await update_schtask(message_to_server)
            logger.info("Response saved to local database due to lack of WebSocket connection (Possibly a Scheduled task)")

        # Start the command using subprocess and provide the password via stdin
        result = subprocess.run(command, input=f"{password}\n", text=True, capture_output=True)

        if result.returncode != 0:
            logger.error(f"Command failed with return code {result.returncode}: {result.stderr}")
            return

        output = result.stdout

        # Log the raw command output
        logger.info(f"Command output:\n{output}")

        # Split output into lines and filter for the summary message
        summary_message = None
        for line in output.splitlines():
            try:
                message = json.loads(line)
                if message.get("message_type") == "summary":
                    summary_message = message
                    break  # Stop after finding the first summary
            except json.JSONDecodeError:
                continue  # Skip non-JSON lines

        if summary_message:
            logger.info(f"Parsed restore summary output: {summary_message}")

            if command_history:
                await save_command('do_local_repo_restore', params, summary_message)

            # Create a message to send to the server
            message_to_server = {
                "task_uuid": task_uuid, # non-persistent, move out to local DB later
                "type": "response_local_repo_restore",  # Define the message type for restore
                "repo_path": repo_path,
                "restore_output": summary_message,
                "task_status": "completed",
            }

            if not optype.startswith("schedule_") and websocket.state == websockets.protocol.State.OPEN:
                # If websocket is available, send the response to the server via WebSocket
                await websocket.send(json.dumps(message_to_server, indent=2))
                logger.info("Response sent over WebSocket.")
            else:
                # WebSocket is may not be available, save the response to local database
                await update_schtask(message_to_server)
                logger.info("Response saved to local database due to lack of WebSocket connection.")

        else:
            logger.error("No JSON found in the command output.")

    except subprocess.TimeoutExpired:
        logger.error("Timeout while waiting for the restore command.")
    except Exception as e:
        logger.error(f"Failed to execute command: {e}")

async def handle_do_s3_repo_backup(params, websocket=None):
    task_uuid = str(uuid.uuid4())  # Generate a unique task UUID for this particular restore task
    logger.info(f"Received request to perform S3 repo backup for bucket: {params['bucket_name']}")

    bucket_name = params.get('bucket_name')
    aws_access_key_id = params.get('aws_access_key_id')
    aws_secret_access_key = params.get('aws_secret_access_key')
    aws_session_token = params.get('aws_session_token')
    region = params.get('region')
    password = params.get('password')
    paths = params.get('paths', [])
    exclude = params.get('exclude', [])
    tags = params.get('tags', [])  # Optional tags
    custom_options = params.get('custom_options', [])
    command_history = params.get('command_history', True)
    optype = params.get("type")

    if not aws_access_key_id or not aws_secret_access_key or not region or not bucket_name:
        logger.error("AWS credentials, region, and bucket name are required.")
        return  # Log the error and return

    # For validation whether repo exists
    # Create a new session with the specified credentials
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token  # Include session token if provided
    )

    # Create an S3 resource with the specified region
    s3 = session.resource('s3', region_name=region)

    # Initialize a flag to determine if the bucket exists
    bucket_exists = False

    try:
        # Check if the bucket exists
        s3.meta.client.head_bucket(Bucket=bucket_name)
        logger.info(f"Bucket {bucket_name} already exists.")
        bucket_exists = True
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
                logger.error(f"Bucket {bucket_name} does not exist and needs to be created using API init")
                return {"error": f"Bucket {bucket_name} does not exist."}
        elif e.response['Error']['Code'] == 'InvalidAccessKeyId':
            logger.error("Invalid AWS Access Key ID provided.")
            return {"error": "Invalid AWS Access Key ID."}
        else:
            logger.error(f"Failed to access bucket: {e}")
            return {"error": str(e)}
        
    # Construct RESTIC_REPOSITORY from attrs.
    restic_repo = f"s3:s3.{region}.amazonaws.com/{bucket_name}"

    try:
        # Create a message to send to the server
        message_to_server = {
            "task_uuid": task_uuid, # non-persistent, move out to local DB later
            "type": "response_s3_repo_backup",  # Define the message type for restore
            "s3_url": restic_repo,
            "backup_output": "",
            "task_status": "processing",
        }

        # send first message
        if not optype.startswith("schedule_") and websocket.state == websockets.protocol.State.OPEN:
            await websocket.send(json.dumps(message_to_server, indent=2))
            logger.info("Response sent over WebSocket.")
        else:
            await update_schtask(message_to_server)
            logger.info("Response saved to local database due to lack of WebSocket connection (Possibly a Scheduled task)")

        # Check if the bucket exists before executing snapshots
        if not bucket_exists:
            return {"error": f"Bucket {bucket_name} does not exist. Cannot perform backup"}

        # Set environment variables using env as a dict
        env = os.environ.copy()  # Copy existing environment variables
        """
        # For credentials
        ```
        aws sts assume-role --role-arn arn:aws:iam::541109128454:role/ResticS3AccessRole --role-session-name RESTIC_SESSION_1
        ```
        """
        env.update({
            'AWS_ACCESS_KEY_ID': aws_access_key_id,
            'AWS_SECRET_ACCESS_KEY': aws_secret_access_key,
            'AWS_SESSION_TOKEN': aws_session_token if aws_session_token else '',
            'RESTIC_REPOSITORY': restic_repo,
            'RESTIC_PASSWORD': password
        })

        # Build the backup command
        command = [restic_path, 'backup', '--json'] + paths

        # Append each exclusion separately
        for ex in exclude:
            command += ['--exclude', ex]

        if custom_options:
            command += custom_options        

        if tags:
            command += ['--tag'] + tags

        logger.info(f"Executing backup command: {command}")

        # Start the command using subprocess and provide the password via stdin
        result = subprocess.run(command, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            if "repository master key and config already initialized" in result.stderr:
                logger.info(f"Repository at {restic_repo} already initialized.")
                return f"Repository at {restic_repo} already initialized."
            logger.error(f"Command failed with return code {result.returncode}: {result.stderr}")
            return f"Command failed: {result.stderr}"

        output = result.stdout

        # Log the raw command output
        logger.info(f"Command output:\n{output}")

        # Split output into lines and filter for the summary message
        summary_message = None
        for line in output.splitlines():
            try:
                message = json.loads(line)
                if message.get("message_type") == "summary":
                    summary_message = message
                    break  # Stop after finding the first summary
            except json.JSONDecodeError:
                continue  # Skip non-JSON lines

        if summary_message:
            logger.info(f"Parsed restore summary output: {summary_message}")

            if command_history:
                await save_command('do_s3_repo_backup', params, summary_message)

            # Create a message to send to the server
            message_to_server = {
                "task_uuid": task_uuid, # non-persistent, move out to local DB later
                "type": "response_s3_repo_backup",  # Define the message type for restore
                "s3_url": restic_repo,
                "backup_output": summary_message,
                "task_status": "completed",
            }

            if not optype.startswith("schedule_") and websocket.state == websockets.protocol.State.OPEN:
                # If websocket is available, send the response to the server via WebSocket
                await websocket.send(json.dumps(message_to_server, indent=2))
                logger.info("Response sent over WebSocket.")
            else:
                # WebSocket is may not be available, save the response to local database
                await update_schtask(message_to_server)
                logger.info("Response saved to local database due to lack of WebSocket connection.")

        else:
            logger.error("No JSON found in the command output.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run command: {e}")
        return {"error": f"Failed to run command: {e}"}
    except subprocess.TimeoutExpired:
        logger.error("Timeout while executing the command.")
        return {"error": "Timeout while executing the command"}
    except botocore.exceptions.ClientError as e:
        logger.error(f"Client error occurred: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Failed to execute operation: {e}")
        return {"error": str(e)}

async def handle_do_s3_repo_restore(params, websocket=None):
    task_uuid = str(uuid.uuid4())  # Generate a unique task UUID for this particular restore task

    logger.info(f"Received request to perform S3 repo restore for bucket: {params['bucket_name']}")

    bucket_name = params.get('bucket_name')
    aws_access_key_id = params.get('aws_access_key_id')
    aws_secret_access_key = params.get('aws_secret_access_key')
    aws_session_token = params.get('aws_session_token')
    region = params.get('region')
    password = params.get('password')
    snapshot_id = params.get('snapshot_id', 'latest')  # Default to 'latest' if no snapshot_id is provided
    target_path = params.get('target_path', '.')  # Where to restore the files
    exclude = params.get('exclude', [])
    include = params.get('include', [])
    custom_options = params.get('custom_options', [])
    command_history = params.get('command_history', True)
    optype = params.get("type")

    if not aws_access_key_id or not aws_secret_access_key or not region or not bucket_name:
        logger.error("AWS credentials, region, and bucket name are required.")
        return  # Log the error and return

    # Create a new session with the specified credentials
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token  # Include session token if provided
    )

    # Create an S3 resource with the specified region
    s3 = session.resource('s3', region_name=region)

    # Check if the bucket exists
    try:
        s3.meta.client.head_bucket(Bucket=bucket_name)
        logger.info(f"Bucket {bucket_name} exists, proceeding with restore.")
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.error(f"Bucket {bucket_name} does not exist.")
            return {"error": f"Bucket {bucket_name} does not exist."}
        logger.error(f"Failed to access bucket: {e}")
        return {"error": str(e)}

    # Construct the RESTIC_REPOSITORY from bucket attributes.
    restic_repo = f"s3:s3.{region}.amazonaws.com/{bucket_name}"

    # Set environment variables using env as a dict
    env = os.environ.copy()  # Copy existing environment variables
    env.update({
        'AWS_ACCESS_KEY_ID': aws_access_key_id,
        'AWS_SECRET_ACCESS_KEY': aws_secret_access_key,
        'AWS_SESSION_TOKEN': aws_session_token if aws_session_token else '',
        'RESTIC_REPOSITORY': restic_repo,
        'RESTIC_PASSWORD': password
    })

    # Build the restore command
    command = [restic_path, 'restore', snapshot_id, '--target', target_path, '--json']

    # Append each exclusion separately
    for ex in exclude:
        command += ['--exclude', ex]

    # Append each inclusion separately
    for inc in include:
        command += ['--include', inc]

    if custom_options:
        command += custom_options

    logger.info(f"Executing restore command: {command}")

    try:
        # Create a message to send to the server
        message_to_server = {
            "task_uuid": task_uuid, # non-persistent, move out to local DB later
            "type": "response_s3_repo_restore",  # Define the message type for restore
            "s3_url": restic_repo,
            "restore_output": "",
            "task_status": "processing",
        }

        # send first message
        if not optype.startswith("schedule_") and websocket.state == websockets.protocol.State.OPEN:
            await websocket.send(json.dumps(message_to_server, indent=2))
            logger.info("Response sent over WebSocket.")
        else:
            await update_schtask(message_to_server)
            logger.info("Response saved to local database due to lack of WebSocket connection (Possibly a Scheduled task)")

        # Start the command using subprocess and provide the password via stdin
        result = subprocess.run(command, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Command failed with return code {result.returncode}: {result.stderr}")
            return f"Command failed: {result.stderr}"

        output = result.stdout

        # Log the raw command output
        logger.info(f"Command output:\n{output}")

        # Split output into lines and filter for the summary message
        summary_message = None
        for line in output.splitlines():
            try:
                message = json.loads(line)
                if message.get("message_type") == "summary":
                    summary_message = message
                    break  # Stop after finding the first summary
            except json.JSONDecodeError:
                continue  # Skip non-JSON lines

        if summary_message:
            logger.info(f"Parsed restore summary output: {summary_message}")
            
            if command_history:
                await save_command('do_s3_repo_restore', params, summary_message)

            # Create a message to send to the server
            message_to_server = {
                "task_uuid": task_uuid, # non-persistent, move out to local DB later
                "type": "response_s3_repo_restore",  # Define the message type for restore
                "s3_url": restic_repo,
                "restore_output": summary_message,
                "task_status": "completed",
            }

            if not optype.startswith("schedule_") and websocket.state == websockets.protocol.State.OPEN:
                # If websocket is available, send the response to the server via WebSocket
                await websocket.send(json.dumps(message_to_server, indent=2))
                logger.info("Response sent over WebSocket.")
            else:
                # WebSocket is may not be available, save the response to local database
                await update_schtask(message_to_server)
                logger.info("Response saved to local database due to lack of WebSocket connection.")

        else:
            logger.error("No JSON found in the command output.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run command: {e}")
        return {"error": f"Failed to run command: {e}"}
    except subprocess.TimeoutExpired:
        logger.error("Timeout while executing the command.")
        return {"error": "Timeout while executing the command"}
    except botocore.exceptions.ClientError as e:
        logger.error(f"Client error occurred: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Failed to execute operation: {e}")
        return {"error": str(e)}