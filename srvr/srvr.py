import logging
from fastapi import FastAPI, WebSocket, Query
from strawberry.fastapi import GraphQLRouter
import strawberry
from typing import List
from srvr.auth import auth_router, verify_access_token
from srvr.backup_recovery import BackupMutations, BackupQueries
from srvr.comms import manager
from srvr.backup_recovery.disaster_recovery import DRMonitor
import asyncio
from pathlib import Path

# MongoDB setup
from srvr.backup_recovery.mongo_setup import (
    status_collection
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI setup
app = FastAPI()

# Initialize the DR monitor
# Use an absolute path for the config file
dr_configuration = Path(__file__).parent / 'backup_recovery' / 'dr.jsonc'
dr_monitor = DRMonitor(str(dr_configuration), manager)  # Path to your DR config file

# Assign the DRMonitor's methods as the event handlers
"""
We are simply passing connection and disconnection events from the ConnectionManager to the DRMonitor so it can track the connection times of each agent.
"""
manager.on_connect = dr_monitor.handle_connect
manager.on_disconnect = dr_monitor.handle_disconnect

# REST: Token acquisition request setup & endpoint for user authentication
app.include_router(auth_router)

background_task = None

@app.on_event("startup")
async def startup_event():
    await manager.connect_to_rabbit()
    # Start the DR monitor in the background
    global background_task
    background_task = asyncio.create_task(dr_monitor.monitor_disconnects())  # Run monitoring as a background task

@app.on_event("shutdown")
async def shutdown_event():
    if background_task:
        background_task.cancel()  # Gracefully cancel the background task
        logger.info("DR monitor task canceled.")
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