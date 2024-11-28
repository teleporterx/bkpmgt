import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from strawberry.fastapi import GraphQLRouter
import strawberry
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List
from srvr.auth import auth_router, verify_access_token
from srvr.backup_recovery import BackupMutations, BackupQueries
from srvr.comms import manager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB setup
MONGO_DETAILS = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
db = client["bkpmgt_db"]
status_collection = db["client_status"]

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
    org: str

# Define the main mutation class
# Pass different mutation classes as args. to include them (Multiple Inheritance)
@strawberry.type
class Mutation(BackupMutations):  # Directly inherit from BackupMutations
    """
    The Mutation class inherits from BackupMutations, 
    enabling the reuse and modularization of mutation logic.
    
    Multiple inheritance can be used here to combine mutations 
    from different sources, e.g., if you want to split backup-related 
    mutations, user-related mutations, etc., into separate classes.
    """
    pass

@strawberry.type
class Query(BackupQueries):
    @strawberry.field
    async def get_client_status(self, system_uuid: str) -> ClientStatus:
        result = await status_collection.find_one({"system_uuid": system_uuid})
        if result:
            # Include the org field in the response
            return ClientStatus(
                system_uuid=result["system_uuid"], 
                status=result["status"],
                org=result.get("org")  # Include org if it's present in the database
            )
        return ClientStatus(system_uuid=system_uuid, status="not found", org=None)  # Handle case when org is missing

    @strawberry.field
    async def get_all_clients(self) -> List[ClientStatus]:
        clients = []
        async for client in status_collection.find():
            # Include the org field for each client in the response
            clients.append(ClientStatus(
                system_uuid=client["system_uuid"], 
                status=client["status"],
                org=client.get("org")  # Safely access the org field
            ))
        return clients
    
    @strawberry.field
    async def get_org_clients(self, org: str) -> List[ClientStatus]:
        # Query clients by the org field
        clients = []
        async for client in status_collection.find({"org": org}):  # Use org filter in the query
            clients.append(ClientStatus(
                system_uuid=client["system_uuid"], 
                status=client["status"],
                org=client.get("org")  # Include the org field
            ))
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