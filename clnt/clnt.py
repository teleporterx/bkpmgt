# clnt.py
import logging
import asyncio
import websockets
import json
import signal
import aio_pika
from sys_utils import *
import requests  # Import requests for HTTP calls
from fastapi import FastAPI
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import sys
from backup_utils import *

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load the configuration
config = load_config()

# Accessing SRVR_IP & ORG from the loaded config
SRVR_IP = config.get('SRVR_IP')
ORG = config.get('ORG')

# Check if SRVR_IP exists in the config, otherwise exit with a message
if not SRVR_IP:
    logger.error("SRVR_IP not found in config. Exiting.")
    sys.exit("SRVR_IP configuration missing!")

logger.info(f"config loaded! .. \n\n-x-x-\nSRVR IP: {SRVR_IP}\nORG    : {ORG}\n-x-x-\n")

# Global flag to control the running state of the agent
running = True

# API for Web-GUI
app = FastAPI()

static_directory = get_static_directory()

# Mount static files like CSS and images
app.mount("/static", StaticFiles(directory=static_directory), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Return the static index.html file from the static directory
    index_path = os.path.join(static_directory, "index.html")
    with open(index_path) as f:
        return HTMLResponse(content=f.read())

# Authentication Setup
async def obtain_jwt(system_uuid, password, max_retries=5, backoff_factor=2, max_backoff_time=120):
    """
    Obtain a JWT token by authenticating with the server.
    Retries on failure with exponential backoff.
    """
    url = f"http://{SRVR_IP}:5000/token"  # Update with your server URL
    retry_attempts = 0

    while retry_attempts < max_retries:
        if not running:
            logger.info("Shutdown triggered during auth. routine...")
            return None  # Exit if shutdown signal received

        try:
            response = requests.post(url, json={"system_uuid": system_uuid, "password": password})
            response.raise_for_status()  # Raise an error for bad responses
            
            token_data = response.json()
            return token_data["access_token"]

        except ConnectionError as e:
            logger.error("Could not connect to the server. Please make sure it is running.")
            logger.error(f"Connection error: {e}")

        except requests.ConnectionError:
            logger.error("Connection refused. The server might be down?? ☠️")

        except Exception as e:
            logger.error("Seems to be a more complex issue ;_;")
            logger.error(f"{e}")

        retry_attempts += 1
        wait_time = min(backoff_factor ** retry_attempts, max_backoff_time)
        logger.info(f"Retrying auth. mechanism in {wait_time} seconds...") # retrying to obtain JWT
        await interruptible_sleep(wait_time)

    logger.error("Failed to authenticate despite multiple attempts.")
    return None

# Shutdown & Restart handlers
def handle_shutdown(signum, frame):
    """
    Signal handler to gracefully shut down the agent process.
    """
    global running
    logger.info("Received shutdown signal. Shutting down gracefully...")
    running = False

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, handle_shutdown)  # Handle Ctrl+C
signal.signal(signal.SIGTERM, handle_shutdown)  # Handle termination signal

@app.post("/shutdown")
async def shutdown():
    """
    Endpoint to trigger the shutdown process.
    """
    os.kill(os.getpid(), signal.SIGINT)
    return {"message": "Shutdown initiated."}

def handle_restart(signum, frame):
    """
    Signal handler to restart the agent process.
    """
    logger.info("Received restart signal. Restarting...")
    # Set a flag or perform any cleanup needed before restarting
    os.execv(sys.executable, ['python'] + sys.argv)  # Restart the application

async def restart_agent():
    os.execv(sys.executable, ['python'] + sys.argv)

@app.post("/restart")
async def restart():
    """
    Endpoint to trigger the restart process.
    """
    # Respond to the request first
    response = {"message": "Restart initiated."}
    await asyncio.sleep(0.1)  # Delay to ensure response is sent
    asyncio.create_task(restart_agent())  # Restart the agent in the background
    return response

async def interruptible_sleep(duration):
    """
    Custom sleep that checks for shutdown signal and interrupts if necessary.
    """
    step = 1  # Sleep in 1-second intervals
    for _ in range(duration):
        if not running:
            break  # Stop sleeping if shutdown signal received
        await asyncio.sleep(step)

async def consume_messages(system_uuid, connection, websocket):
    """
    Consume messages from the RabbitMQ queue for the given system UUID.
    """
    async with connection:
        channel = await connection.channel()  # Create a channel
        queue_name = f"queue_{system_uuid}"
        
        # Declare the queue
        queue = await channel.declare_queue(queue_name, durable=True)

        # Dispatch table for handling message types
        dispatch_table = {
            "init_local_repo": handle_init_local_repo,
            "get_local_repo_snapshots": handle_get_local_repo_snapshots,
            "do_local_repo_backup": handle_do_local_repo_backup,
            "do_local_repo_restore": handle_do_local_repo_restore,
            "do_s3_repo_backup": handle_do_s3_repo_backup,
            "do_s3_repo_restore": handle_do_s3_repo_restore,
        }

        async for message in queue:
            try:
                async with message.process():
                    message_data = json.loads(message.body.decode())
                    message_type = message_data.get("type")

                    if message_type.startswith("schedule_"):
                        # Write to schedule ledger
                        scheduler = ScheduleManager()
                        await scheduler.handle_scheduled_task(message_data, websocket)
                        command_history = message_data.get('command_history', True)
                        if command_history:
                            await save_scheduled_task(message_data)
                    else:
                        # Regular message handling
                        handler = dispatch_table.get(message_type)
                        if handler:
                            await handler(message_data, websocket)  # Pass websocket instance
                        else:
                            logger.warning(f"Unknown message type: {message_type}")
            except Exception as e:
                logger.error(f"Error processing message: {e}")

async def agent():
    system_uuid = get_system_uuid()
    
    if not system_uuid:
        logger.error("System UUID not found! Exiting...")
        return
    # PATCH: Use dotenv or other mechanisms when deploying to production
    password = "deepdefend_authpass"
    token = await obtain_jwt(system_uuid, password)
    if not token:
        logger.error("Authentication routine failed!! Exiting...") # Failed to obtain JWT token
        return
    
    # This passes the ORG along with system_uuid and token to the server via the WebSocket URL
    bhive_uri = f"ws://{SRVR_IP}:5000/ws/{system_uuid}?token={token}&org={config.get('ORG')}"

    retry_attempts = 0
    backoff_factor = 2
    max_backoff_time = 60  # Cap the backoff time to 60 seconds (for testing)

    rabbit_connection = None  # Initialize rabbit_connection here

    while running:
        try:
            uri = bhive_uri.format(system_uuid=system_uuid)  # Format URI with system_uuid
            async with websockets.connect(uri) as websocket:
                logger.info("Connected to WebSocket server.")

                try:
                    rabbit_connection = await aio_pika.connect_robust(f"amqp://guest:guest@{SRVR_IP}/")
                    consumer_task = asyncio.create_task(consume_messages(system_uuid, rabbit_connection, websocket))  # Pass websocket here

                    retry_attempts = 0  # Reset retry attempts after a successful connection

                    # Agent main loop
                    while running:
                        # You can send data to the WebSocket server if needed
                        # Example: await websocket.send("Some data")
                        # Or some form of inbound message handling

                        if websocket.state != websockets.protocol.State.OPEN:
                            logger.warning("WebSocket connection closed.")
                            break;
                        
                        # Sleep for 5 seconds before the next operation
                        await interruptible_sleep(5)

                except Exception as e:
                    logger.error(f"Failed to connect to RabbitMQ: {e}")
                    if 'consumer_task' in locals():
                        consumer_task.cancel()
                    if rabbit_connection:
                        await rabbit_connection.close()

        except Exception as e:
            logger.error("Looks like the server &/ rabbit is down ☠️")
            if str(e):
                logger.error(f"{e}")
            retry_attempts += 1
            wait_time = min(backoff_factor ** retry_attempts, max_backoff_time)  # Exponential backoff, capped
            logger.info(f"Retrying WebSocket connection in {wait_time} seconds...")
            await interruptible_sleep(wait_time)

    # Cleanup: Cancel the consumer task and close the RabbitMQ connection
    if 'consumer_task' in locals():
        consumer_task.cancel()
    if rabbit_connection:
        await rabbit_connection.close()
    logger.info("RabbitMQ connection closed.")

    if not running:
        logger.info("Graceful shutdown target reached...")

async def run_uvicorn():
    config = uvicorn.Config(app, host="127.0.0.1", port=8080, reload=True)
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(agent(), run_uvicorn())

if __name__ == "__main__":
    asyncio.run(main())