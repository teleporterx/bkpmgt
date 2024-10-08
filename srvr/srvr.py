import logging
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from strawberry.fastapi import GraphQLRouter
from motor.motor_asyncio import AsyncIOMotorClient
import strawberry
from typing import List
import json
import datetime
from datetime import timedelta
import aio_pika

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB setup
MONGO_DETAILS = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
db = client["bkpmgt_db"]
status_collection = db["client_status"]
repo_snapshots_collection = db["repo_snapshots"]
snapshot_contents_collection = db["snapshot_contents"]

# Data Handler class
class DataHandler:
    def __init__(self):
        self.repo_snapshots_collection = repo_snapshots_collection
        self.snapshot_contents_collection = snapshot_contents_collection
        self.dispatch_table = {
            "repo_snapshots": self.handle_repo_snapshots,
            "snapshot_contents": self.handle_snapshot_contents,
        }
        # Start the cleanup task
        asyncio.create_task(self.cleanup_old_data())

    async def cleanup_old_data(self):
        while True:
            await asyncio.sleep(60)  # Wait for 1 min
            cutoff_time = datetime.datetime.now(datetime.timezone.utc) - timedelta(minutes=1)
            logger.info(f"Cutoff time for deletion: {cutoff_time.isoformat()}")

            # Cleanup old repo snapshots
            result_repo_snapshots = await self.repo_snapshots_collection.delete_many({"timestamp": {"$lt": cutoff_time.isoformat()}})
            logger.info(f"Deleted {result_repo_snapshots.deleted_count} old repo snapshots.")

            # Cleanup old snapshot contents
            result_snapshot_contents = await self.snapshot_contents_collection.delete_many({"timestamp": {"$lt": cutoff_time.isoformat()}})
            logger.info(f"Deleted {result_snapshot_contents.deleted_count} old snapshot contents.")

    async def handle_repo_snapshots(self, system_uuid, message):
        logger.info(f"Stored performance metrics for {system_uuid}")

    async def handle_snapshot_contents(self, system_uuid, message):
        logger.info(f"Stored process tree for {system_uuid}")

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

    async def connect_to_rabbit(self):
        try:
            self.rabbit_connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
            self.channel = await self.rabbit_connection.channel()  # Create a channel
            logger.info("Connected to RabbitMQ.")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")

    async def create_queue(self, system_uuid: str):
        queue_name = f"queue_{system_uuid}"
        await self.channel.set_qos(prefetch_count=1)  # Optional: Control message flow
        queue = await self.channel.declare_queue(queue_name, durable=True)
        self.queues[system_uuid] = queue  # Store the reference to the queue
        logger.info(f"Queue created: {queue_name}")
        return queue

    async def connect(self, websocket: WebSocket, system_uuid: str):
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
                await queue.delete()  # Use the delete method on the queue
                logger.info(f"Queue deleted: queue_{system_uuid}")
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

manager = ConnectionManager()

# FastAPI setup
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await manager.connect_to_rabbit()

# WebSocket endpoint
@app.websocket("/ws/{system_uuid}")
async def websocket_endpoint(websocket: WebSocket, system_uuid: str):
    await manager.connect(websocket, system_uuid)
    await manager.receive_data(websocket, system_uuid)

# Strawberry GraphQL setup
@strawberry.type
class ClientStatus:
    system_uuid: str
    status: str

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def allocate_repo_snapshot_task(
        self,
        system_uuid: str,
        repo: str,
        password: str,
    ) -> str:
        # Check if the client is connected
        if system_uuid not in manager.active_connections:
            return "Error: Client not connected"

        # Create a task message
        task_message = {
            "type": "repo_snapshots",
            "repo": repo,
            "password": password,
        }

        # Get the client's queue
        queue = manager.queues.get(system_uuid)
        if not queue:
            return "Error: Queue not found for the client"

        # Publish the task to the client's queue
        await manager.channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(task_message).encode()),
            routing_key=queue.name  # Use the name of the queue as the routing key
        )

        return f"Task allocated to retrieve snapshots for repo: {repo}"

@strawberry.type
class Query:
    @strawberry.field
    async def get_client_status(self, system_uuid: str) -> ClientStatus:
        result = await status_collection.find_one({"system_uuid": system_uuid})
        if result:
            return ClientStatus(system_uuid=result["system_uuid"], status=result["status"])
        return ClientStatus(system_uuid=system_uuid, status="not found")

    @strawberry.field
    async def get_all_clients(self) -> List[ClientStatus]:
        clients = []
        async for client in status_collection.find():
            clients.append(ClientStatus(system_uuid=client["system_uuid"], status=client["status"]))
        return clients

schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)

# Adding the GraphQL endpoint
app.include_router(graphql_app, prefix="/graphql")

ascii_art = """
╭━━╮╱╱╱╭╮╱╭┳━━┳╮╱╱╭┳━━━╮
┃╭╮┃╱╱╱┃┃╱┃┣┫┣┫╰╮╭╯┃╭━━╯
┃╰╯╰╮╱╱┃╰━╯┃┃┃╰╮┃┃╭┫╰━━╮
┃╭━╮┣━━┫╭━╮┃┃┃╱┃╰╯┃┃╭━━╯
┃╰━╯┣━━┫┃╱┃┣┫┣╮╰╮╭╯┃╰━━╮
╰━━━╯╱╱╰╯╱╰┻━━╯╱╰╯╱╰━━━╯
----- NETWORK KIT ------
"""
print(ascii_art)

# Server running on ws://localhost:5000/ws/{system_uuid}