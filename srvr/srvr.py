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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB setup
MONGO_DETAILS = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
db = client["bkpmgt_db"]
status_collection = db["client_status"]
repo_snapshots_collection = db["repo_snapshots"]
snapshot_contnents_collection = db["snapshot_contnents"]

# Data Handler class
class DataHandler:
    def __init__(self):
        self.repo_snapshots_collection = repo_snapshots_collection
        self.snapshot_contnents_collection = snapshot_contnents_collection
        self.dispatch_table = {
            "repo_snapshots": self.handle_repo_snapshots,
            "snapshot_contnents": self.handle_snapshot_contnents,
            # Add more mappings for other types of data
        }
        # Start the cleanup task
        asyncio.create_task(self.cleanup_old_data())

    async def cleanup_old_data(self):
        while True:
            await asyncio.sleep(60)  # Wait for 1 min
            cutoff_time = datetime.datetime.now(datetime.timezone.utc) - timedelta(minutes=1)  # Cutoff time for 1 min ago
            logger.info(f"Cutoff time for deletion: {cutoff_time.isoformat()}")  # Log cutoff time

            # Cleanup old performance metrics
            result_repo_snapshots= await self.performance_metrics_collection.delete_many({"timestamp": {"$lt": cutoff_time.isoformat()}})
            logger.info(f"Deleted {result_repo_snapshots.deleted_count} old repo snapshots.")

            # Cleanup old process trees
            result_snapshot_contnents = await self.process_tree_collection.delete_many({"timestamp": {"$lt": cutoff_time.isoformat()}})
            logger.info(f"Deleted {result_snapshot_contnents.deleted_count} old snapshot contnents.")

    async def handle_repo_snapshots(self, system_uuid, message):
        """ store the data to mongo like this for 
        await self.performance_metrics_collection.insert_one({
            "system_uuid": system_uuid,
            "cpu_usage": message.get("cpu_usage"),
            "memory_usage": message.get("memory_usage"),
            "process_count": message.get("process_count"),
            "timestamp": message.get("timestamp")  # Keep as ISO string
        })
        """
        logger.info(f"Stored performance metrics for {system_uuid}")

    async def handle_snapshot_contnents(self, system_uuid, message):
        # store the data to mongo
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
        self.data_handler = DataHandler()  # Initialize the DataHandler instance

    async def connect(self, websocket: WebSocket, system_uuid: str):
        await websocket.accept()
        self.active_connections[system_uuid] = websocket
        logger.info(f"Client {system_uuid} connected.")
        await status_collection.update_one(
            {"system_uuid": system_uuid},
            {"$set": {"status": "connected"}},
            upsert=True
        )

    async def disconnect(self, system_uuid: str):
        self.active_connections.pop(system_uuid, None)
        logger.info(f"Client {system_uuid} disconnected.")
        await status_collection.update_one(
            {"system_uuid": system_uuid},
            {"$set": {"status": "disconnected"}}
        )

    async def receive_data(self, websocket: WebSocket, system_uuid: str):
        try:
            while True:
                data = await websocket.receive_text()
                logger.info(f"Received message from {system_uuid}: {data}")

                # Parse the incoming message as JSON
                message = json.loads(data)

                # Delegate message handling to DataHandler
                await self.data_handler.handle_message(system_uuid, message)

        except WebSocketDisconnect:
            await self.disconnect(system_uuid)

manager = ConnectionManager()

# FastAPI setup
app = FastAPI()

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

schema = strawberry.Schema(query=Query)
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