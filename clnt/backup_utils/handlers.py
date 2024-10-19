import logging
import subprocess
import json
import re
import os
import boto3 # AWS SDK for Python
import botocore # for exception handling

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_init_local_repo(params, websocket):
    """
    Initialize a local restic repository with a given password and log the output in JSON format when applicable.
    Also, send the initialization output to the server over WebSocket.
    """
    logger.info(f"Initializing Restic repository at: {params['repo_path']}")
    password = params.get('password')
    repo_path = params.get('repo_path')

    command = ['./restic', '-r', repo_path, 'init', '--json']

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


async def handle_get_local_repo_snapshots(params, websocket):
    """
    Handle 'get_local_repo_snapshots' message type with restic and send results to the server.
    """
    logger.info(f"Received task to list snapshots for repo: {params['repo_path']}")

    password = params.get('password')
    repo_path = params.get('repo_path')

    if not password or not repo_path:
        logger.error("Password and repository path are required.")
        return  # No return, just log the error
    
    command = ['./restic', '-r', repo_path, 'snapshots', '--json']

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

            # Create a message to send to the server
            message_to_server = {
                "type": "response_local_repo_snapshots",
                # "systemUuid": system_uuid,  # Send system UUID; this is will be resolved by the server WS
                "repo_path": repo_path,
                "snapshots": snapshots,
            }

            # Send the message over WebSocket
            await websocket.send(json.dumps(message_to_server, indent=2))

        else: # Future: create a message payload with failure output
            logger.error("No JSON found in the command output.")

    except subprocess.TimeoutExpired:
        logger.error("Timeout waiting for password prompt.")
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON output from restic.")
    except Exception as e:
        logger.error(f"Failed to execute command: {e}")

async def handle_do_local_repo_backup(params, websocket):
    logger.info(f"Received request to perform local repo backup for repo: {params['repo_path']}")

    repo_path = params.get('repo_path')
    password = params.get('password')
    paths = params.get('paths', [])  # Get the paths for backup
    exclude = params.get('exclude', [])  # Optional exclude filters
    custom_options = params.get('custom_options', [])  # Any additional options
    """
    tags = params.get('tags', [])  # Optional tags
    """

    if not password or not repo_path:
        logger.error("Password and repository path are required.")
        return  # Log the error and return

    # Build the backup command
    command = ['./restic', '-r', repo_path, 'backup', '--json'] + paths

    # Append each exclusion separately
    for ex in exclude:
        command += ['--exclude', ex]
    
    if custom_options:
        command += custom_options
    
    """
    if include:
        command += ['--include'] + include
    if tags:
        command += ['--tag'] + tags
    """
    
    logger.info(f"this is the command that would be executed {command}")

    try:
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
            logger.info(f"Parsed backup summary output: {summary_message}")

            # Create a message to send to the server
            message_to_server = {
                "type": "response_local_repo_backup",  # Define the message type for backup
                "repo_path": repo_path,
                "backup_output": summary_message,
            }

            # Send the message over WebSocket
            await websocket.send(json.dumps(message_to_server, indent=2))
            logger.info(f"Backup data sent to server for repo: {repo_path}")
        else:
            logger.error("No JSON found in the command output.")

    except subprocess.TimeoutExpired:
        logger.error("Timeout while waiting for the backup command.")
    except Exception as e:
        logger.error(f"Failed to execute command: {e}")