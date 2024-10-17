# comms/conn_manager.py
import logging
import asyncio
from fastapi import WebSocket, WebSocketDisconnect, Query
from motor.motor_asyncio import AsyncIOMotorClient
import json
from datetime import datetime, timedelta, timezone
import aio_pika

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB setup
MONGO_DETAILS = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
db = client["bkpmgt_db"]
status_collection = db["client_status"]
initialized_local_repos_collection = db["initialized_local_repos"] 
initialized_s3_repos_collection = db["initialized_s3_repos"] 
local_repo_snapshots_collection = db["local_repo_snapshots"]
snapshot_contents_collection = db["snapshot_contents"]

# Data Handler class
class DataHandler:
    def __init__(self):
        self.initialized_local_repos_collection = initialized_local_repos_collection
        self.initialized_s3_repos_collection = initialized_s3_repos_collection
        self.repo_snapshots_collection = local_repo_snapshots_collection
        self.snapshot_contents_collection = snapshot_contents_collection
        self.dispatch_table = {
            "response_init_local_repo": self.handle_response_init_local_repo,
            "response_init_s3_repo": self.handle_response_init_s3_repo,
            "response_local_repo_snapshots": self.handle_response_local_repo_snapshots,
            "snapshot_contents": self.handle_snapshot_contents,
        }
        # Start the cleanup task
        asyncio.create_task(self.cleanup_old_data())

    async def cleanup_old_data(self):
        while True:
            await asyncio.sleep(60)  # Wait for 1 min
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=1)  # Updated line
            # logger.info(f"Cutoff time for deletion: {cutoff_time.isoformat()}")

            # Cleanup old repo snapshots
            # Directly use the datetime object for the query
            result_repo_snapshots = await self.repo_snapshots_collection.delete_many({"response_timestamp": {"$lt": cutoff_time}})
            # logger.info(f"Deleted {result_repo_snapshots.deleted_count} old repo snapshots.")

            # Cleanup old snapshot contents
            result_snapshot_contents = await self.snapshot_contents_collection.delete_many({"timestamp": {"$lt": cutoff_time}})
            # logger.info(f"Deleted {result_snapshot_contents.deleted_count} old snapshot contents.")

    async def handle_response_init_local_repo(self, system_uuid, message):
        response_timestamp = datetime.now(timezone.utc)
        summary = message.get("summary", {})

        # Log or process the repo initialization as needed
        logger.info(f"Repo initialized for {system_uuid} : {summary}")

        # Store the repo initialization data in MongoDB
        document = {
            "systemUuid": system_uuid,
            "response_timestamp": response_timestamp,
            "summary": summary,
        }

        # No need to check for existing records as client-side handling will ever allow only one repo to exist in absolute path
        try:
            await self.initialized_local_repos_collection.update_one(
                {"systemUuid": system_uuid},
                {"$set": document},
                upsert=True
            )
            logger.info(f"Stored repo initialization data for {system_uuid}")
        except Exception as e:
            logger.error(f"Error storing repo initialization data: {e}")

    async def handle_response_local_repo_snapshots(self, system_uuid, message):
        snapshots = message.get("snapshots", [])
        repo_path = message.get("repo_path")  # Retrieve the repo name
        response_timestamp = datetime.now(timezone.utc)  # Get current timestamp

        # Check if there's already an existing document for this systemUuid and repo_path
        existing_document = await self.repo_snapshots_collection.find_one({
            "systemUuid": system_uuid,
            "repo_path": repo_path
        })
        if existing_document:
            # Compare existing snapshots with new snapshots
            if existing_document.get("snapshots") == snapshots:
                logger.info(f"No changes detected for {system_uuid} on repo path {repo_path}. Skipping update.")
                return  # No need to update if snapshots are the same
        # Document structure to insert/upsert
        document = {
            "systemUuid": system_uuid,
            "response_timestamp": response_timestamp,
            "repo_path": repo_path,
            "snapshots": snapshots  # Directly include snapshots
        }

        # Upsert the document (insert or update)
        await self.repo_snapshots_collection.update_one(
            {"systemUuid": system_uuid, "repo_path": repo_path},  # Query to find the document
            {"$set": document},  # Update the document with the new data
            upsert=True  # Create the document if it does not exist
        )
        
        logger.info(f"Stored repo snapshot response for {system_uuid} for repo path {repo_path}")

    async def handle_response_init_s3_repo(self, system_uuid, message):
        response_timestamp = datetime.now(timezone.utc)
        summary = message.get("summary", {})

        # Log or process the repo initialization as needed
        logger.info(f"Repo initialized for {system_uuid} : {summary}")

        # Store the repo initialization data in MongoDB
        document = {
            "systemUuid": system_uuid,
            "response_timestamp": response_timestamp,
            "summary": summary,
        }

        # No need to check for existing records as client-side handling will ever allow only one repo to exist in absolute path
        try:
            await self.initialized_s3_repos_collection.update_one(
                {"systemUuid": system_uuid},
                {"$set": document},
                upsert=True
            )
            logger.info(f"Stored repo initialization data for {system_uuid}")
        except Exception as e:
            logger.error(f"Error storing repo initialization data: {e}")

    async def handle_snapshot_contents(self, system_uuid, message):
        logger.info(f"Stored snapshot contents response for {system_uuid}")

    async def handle_message(self, system_uuid, message):
        message_type = message.get("type")
        handler = self.dispatch_table.get(message_type)
        if handler:
            await handler(system_uuid, message)
        else:
            logger.warning(f"Unknown message type {message_type} from {system_uuid}")

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

        await websocket.accept()
        self.active_connections[system_uuid] = websocket
        logger.info(f"Client {system_uuid} connected.")
        await status_collection.update_one(
            {"system_uuid": system_uuid},
            {"$set": {"status": "connected"}},
            upsert=True
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
                await self.data_handler.handle_message(system_uuid, message)

        except WebSocketDisconnect:
            await self.disconnect(system_uuid)
        except RuntimeError as e:
            logger.error(f"Runtime error for {system_uuid}: {e}")

manager = ConnectionManager()
