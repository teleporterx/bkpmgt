import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from strawberry.fastapi import GraphQLRouter
import strawberry
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List
from auth import auth_router, verify_access_token
from backup_recovery import BackupMutations
from comms import manager

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

# FastAPI setup
app = FastAPI()
# REST: Token acquisition request setup & endpoint for user authentication
app.include_router(auth_router)

@app.on_event("startup")
async def startup_event():
    await manager.connect_to_rabbit()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down server... /ws/ will be closed")

# WebSocket endpoint
@app.websocket("/ws/{system_uuid}")
async def websocket_endpoint(websocket: WebSocket, system_uuid: str, token: str = Query(...)):
    # Verify the JWT token
    payload = verify_access_token(token)
    if payload is None:
        # Close connection for unauthorized clients
        await websocket.close(code=4001)  # Custom code for unauthorized access
        return
    
    await manager.connect(websocket, system_uuid)
    await manager.receive_data(websocket, system_uuid)

# Strawberry GraphQL setup
@strawberry.type
class ClientStatus:
    system_uuid: str
    status: str

# Define the main mutation class
# Pass different mutation classes as args. to include them (Multiple Inheritance)
@strawberry.type
class Mutation(BackupMutations):  # Directly inherit from BackupMutations
    pass

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