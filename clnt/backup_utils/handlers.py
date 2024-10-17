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
            await websocket.send(json.dumps(message_to_server))

        else: # Future: create a message payload with failure output
            logger.error("No JSON found in the command output.")

    except subprocess.TimeoutExpired:
        logger.error("Timeout waiting for password prompt.")
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON output from restic.")
    except Exception as e:
        logger.error(f"Failed to execute command: {e}")

async def handle_init_s3_repo(params, websocket):
    """
    Initialize an S3 Restic repository by running separate 'export' commands for AWS credentials and Restic settings, followed by 'restic init'.
    """
    logger.info(f"Initializing S3 Restic repository in bucket: {params['bucket_name']}")

    # Extract the required data from the params
    aws_access_key_id = params.get('aws_access_key_id')
    aws_secret_access_key = params.get('aws_secret_access_key')
    aws_session_token = params.get('aws_session_token')  # Optional session token
    region = params.get('region')
    bucket_name = params.get('bucket_name')
    password = params.get('password')

    if not aws_access_key_id or not aws_secret_access_key or not region or not bucket_name or not password:
        logger.error("Missing essential initialization data!")
        return

    # Create a new session with the specified credentials
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token  # Include session token if provided
    )

    # Create an S3 resource with the specified region
    s3 = session.resource('s3', region_name=region)

    try:
        # Check if the bucket exists
        s3.meta.client.head_bucket(Bucket=bucket_name)
        logger.info(f"Bucket {bucket_name} already exists.")
    except botocore.exceptions.ClientError as e:
        # Handle specific error codes
        if e.response['Error']['Code'] == '404':
            # Bucket does not exist, so create it
            logger.info(f"Bucket {bucket_name} does not exist. Creating it...")
            s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={
                'LocationConstraint': region
            })
            logger.info(f"Bucket {bucket_name} created successfully.")
        elif e.response['Error']['Code'] == 'InvalidAccessKeyId':
            logger.error("Invalid AWS Access Key ID provided.")
            return {"error": "Invalid AWS Access Key ID."}
        else: # Will probably get triggered due to invalid temporary AWS credentials
            logger.error(f"Failed to access bucket: {e}")
            return {"error": str(e)}

    # Construct RESTIC_REPOSITORY from attrs.
    restic_repo = f"s3:s3.{region}.amazonaws.com/{bucket_name}"

    try:
        # Set environment variables using env as a dict; ditched os.environ dictionary assignment cause it only affects the current Python process
        env = os.environ.copy()  # Copy existing environment variables
        env.update({
            'AWS_ACCESS_KEY_ID': aws_access_key_id,
            'AWS_SECRET_ACCESS_KEY': aws_secret_access_key,
            'AWS_SESSION_TOKEN': aws_session_token if aws_session_token else '',
            'RESTIC_REPOSITORY': restic_repo,
            'RESTIC_PASSWORD': password
        })

        # Run the 'restic s3:<params> init --json' command after setting environment variables
        command = ['./restic', 'init', '--json']
        # env dict passed to subprocess using env parameter; it is platform independent
        # result = subprocess.run(command, env=env, shell=True, capture_output=True, text=True) # with shell=True the command runs in a subshell and env isn't accounted for
        result = subprocess.run(command, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Command failed with return code {result.returncode}: {result.stderr}")
            return {"error": f"Command failed: {result.stderr}"}

        # Log success message
        logger.info(f"Successfully initialized S3 restic repository at {restic_repo}")
        logger.info(f"Command output:\n{result.stdout}")

        # Create a message to send to the server
        message_to_server = {
            "type": "response_init_s3_repo",  # Define the message type for S3 repo initialization
            "summary": json.loads(result.stdout)  # Include the parsed JSON output
        }

        # Send the message to the server over WebSocket
        await websocket.send(json.dumps(message_to_server, indent=2))
        logger.info(f"S3 repo initialization data sent to server for repo: {restic_repo}")

        return {"message": f"Successfully initialized S3 restic repository at {restic_repo}"}

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run command: {e}")
        return {"error": f"Failed to run command: {e}"}
    except subprocess.TimeoutExpired:
        logger.error("Timeout while initializing the repository.")
        return {"error": "Timeout while initializing the repository"}
    except botocore.exceptions.ClientError as e:
        logger.error(f"Client error occurred: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Failed to initialize repository: {e}")
        return {"error": str(e)}
    # Need to add response mech.