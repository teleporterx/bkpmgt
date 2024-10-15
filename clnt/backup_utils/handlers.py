import logging
import subprocess
import json
import re

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_repo_snapshots(params, websocket):
    """
    Handle 'repo_snapshots' message type with restic and send results to the server.
    """
    logger.info(f"Received task to list snapshots for repo: {params['repo']}")

    password = params.get('password')
    command = ['./restic', '-r', params['repo'], 'snapshots', '--json']

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
                "type": "repo_snapshots",
                # "systemUuid": system_uuid,  # Send system UUID; this is will be resolved by the server WS
                "repo_path": params['repo'],
                "snapshots": snapshots,
            }

            # Send the message over WebSocket
            await websocket.send(json.dumps(message_to_server))

        else:
            logger.error("No JSON found in the command output.")

    except subprocess.TimeoutExpired:
        logger.error("Timeout waiting for password prompt.")
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON output from restic.")
    except Exception as e:
        logger.error(f"Failed to execute command: {e}")