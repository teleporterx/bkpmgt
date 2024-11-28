# comms/conn_manager.py
import logging
from fastapi import WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorClient
import json
import aio_pika
from srvr.backup_recovery.handlers import BackupHandlers # avoid the circular dependency during module initialization by moving this inside the DataHandler Class

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB setup (only for client_status)
MONGO_DETAILS = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
db = client["bkpmgt_db"]
status_collection = db["client_status"]

# Data Handler class
class DataHandler:
    def __init__(self):
        self.backup_handlers = BackupHandlers()
        # Add other handlers as needed
        self.dispatch_table = { # to invoke corresponding handlers
            **self.backup_handlers.dispatch_table,  # Include backup handlers
            # Add other message types here
            "other_message_type": self.handle_other_message_type,
            # Add more as necessary
        }

    async def handle_other_message_type(self, system_uuid, message):
        # Handle other message types here
        logger.info(f"Handling other message type for {system_uuid}: {message}")
        # Implementation...

    async def handle_message(self, system_uuid, message, org):
        message_type = message.get("type")
        handler = self.dispatch_table.get(message_type)
        if handler:
            await handler(system_uuid, message, org)
        else:
            logger.warning(f"Unknown message type {message_type} from {system_uuid} in org {org}")

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}
        self.data_handler = DataHandler()
        self.rabbit_connection = None
        self.channel = None
        self.queues = {}
        self.rabbit_connected = False  # Flag to track RabbitMQ connection status

    async def connect_to_rabbit(self):
        try:
            self.rabbit_connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
            self.channel = await self.rabbit_connection.channel()  # Create a channel
            self.rabbit_connected = True  # Set the flag to True
            logger.info("Connected to RabbitMQ.")
        except Exception as e:
            self.rabbit_connected = False  # Set the flag to False on failure
            logger.error(f"Failed to connect to RabbitMQ: {e}")

    async def create_queue(self, system_uuid: str):
        if not self.rabbit_connected:
            logger.warning(f"Cannot create queue for {system_uuid}: RabbitMQ is down.")
            return None
        queue_name = f"queue_{system_uuid}"
        await self.channel.set_qos(prefetch_count=1)  # Optional: Control message flow
        queue = await self.channel.declare_queue(queue_name, durable=True)
        self.queues[system_uuid] = queue  # Store the reference to the queue
        logger.info(f"Queue created: {queue_name}")
        return queue

    async def connect(self, websocket: WebSocket, system_uuid: str):
        # Check if RabbitMQ is connected
        if not self.rabbit_connected:
            logger.warning(f"Connection denied for {system_uuid}: RabbitMQ is down.")
            await websocket.close(code=4000)  # Close the connection with a custom code
            return
        # Extract the 'org' query parameter from the WebSocket connection
        org = websocket.query_params.get("org")  # This retrieves the 'org' parameter from the URL

        # Check if 'org' was provided
        if not org:
            logger.warning(f"Connection from {system_uuid} denied: 'org' parameter is missing.")
            await websocket.close(code=4001)  # Close with an error code if 'org' is missing
            return

        await websocket.accept()
        self.active_connections[system_uuid] = websocket
        logger.info(f"Client {system_uuid} connected with org: {org}.")
        # Update the client's status in MongoDB, including the 'org' field
        await status_collection.update_one(
            {"system_uuid": system_uuid},
            {
                "$set": {
                    "status": "connected",
                    "org": org  # Save the 'org' field
                }
            },
            upsert=True # If no document is found, create a new one
        )
        await self.create_queue(system_uuid)  # Create a queue for this client

    async def disconnect(self, system_uuid: str):
        websocket = self.active_connections.pop(system_uuid, None)
        if websocket:
            logger.info(f"Client {system_uuid} disconnected.")
            await status_collection.update_one(
                {"system_uuid": system_uuid},
                {"$set": {"status": "disconnected"}}
            )
            
            # Delete the client's queue
            queue = self.queues.pop(system_uuid, None)
            if queue:
                try:
                    # await queue.delete()  # Attempt to delete the queue: OG
                    # logger.info(f"Queue deleted: queue_{system_uuid}")
                    await self.channel.queue_delete(queue.name)  # Directly delete the queue
                    logger.info(f"Queue forcefully deleted: queue_{system_uuid}")

                except Exception as e:
                    logger.error(f"Failed to forcefully delete queue {queue.name}: {e}")
                # except aio_pika.exceptions.ChannelPreconditionFailed:
                #     logger.warning(f"Queue {queue.name} not deleted: it contains pending tasks.")
            else:
                logger.warning("Queue not found for deletion.")

    async def receive_data(self, websocket: WebSocket, system_uuid: str):
        try:
            while True:
                data = await websocket.receive_text()
                logger.info(f"Received message from {system_uuid}: {data}")

                message = json.loads(data)
                org = websocket.query_params.get("org")  # This retrieves the 'org' parameter from the URL
                await self.data_handler.handle_message(system_uuid, message, org)

        except WebSocketDisconnect:
            await self.disconnect(system_uuid)
        except RuntimeError as e:
            logger.error(f"Runtime error for {system_uuid}: {e}")

manager = ConnectionManager()
