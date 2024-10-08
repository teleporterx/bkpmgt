import datetime
import logging
import asyncio
import websockets
import json
import signal
import aio_pika
from sys_utils.uuid_info import get_system_uuid

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global flag to control the running state of the agent
running = True

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

async def interruptible_sleep(duration):
    """
    Custom sleep that checks for shutdown signal and interrupts if necessary.
    """
    step = 1  # Sleep in 1-second intervals
    for _ in range(duration):
        if not running:
            break  # Stop sleeping if shutdown signal received
        await asyncio.sleep(step)

async def consume_messages(system_uuid, connection):
    """
    Consume messages from the RabbitMQ queue for the given system UUID.
    """
    async with connection:
        channel = await connection.channel()  # Create a channel
        queue_name = f"queue_{system_uuid}"
        
        # Declare the queue
        queue = await channel.declare_queue(queue_name, durable=True)

        async for message in queue:
            async with message.process():
                # Process the message
                logger.info(f"Received message: {message.body.decode()}")
                # Add your message processing logic here
                # For example: store in a database, trigger actions, etc.

async def agent():
    bhive_uri = "ws://192.168.0.101:5000/ws/{system_uuid}"  # Point to the server IP
    system_uuid = get_system_uuid()
    
    if not system_uuid:
        logger.error("System UUID not found! Exiting...")
        return
    
    retry_attempts = 0
    backoff_factor = 2
    max_backoff_time = 60  # Cap the backoff time to 60 seconds

    rabbit_connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    
    consumer_task = asyncio.create_task(consume_messages(system_uuid, rabbit_connection))

    while running:
        try:
            uri = bhive_uri.format(system_uuid=system_uuid)  # Format URI with system_uuid
            async with websockets.connect(uri) as websocket:
                logger.info("Connected to WebSocket server.")
                retry_attempts = 0  # Reset retry attempts after a successful connection

                # Agent main loop
                while running:
                    # You can send data to the WebSocket server if needed
                    # Example: await websocket.send("Some data")

                    # Sleep for 5 seconds before the next operation
                    await interruptible_sleep(5)

        except Exception as e:
            logger.error(f"Looks like the server is down ☠️")
            if str(e):
                logger.error(f"{e}")
            retry_attempts += 1
            wait_time = min(backoff_factor ** retry_attempts, max_backoff_time)  # Exponential backoff, capped
            logger.info(f"Retrying in {wait_time} seconds...")
            await interruptible_sleep(wait_time)

    # Cleanup: Cancel the consumer task and close the RabbitMQ connection
    consumer_task.cancel()
    await rabbit_connection.close()
    logger.info("RabbitMQ connection closed.")

    if not running:
        logger.info("Graceful shutdown target reached...")

# Call to start agent
def run_agent():
    asyncio.run(agent())

if __name__ == "__main__":
    run_agent()