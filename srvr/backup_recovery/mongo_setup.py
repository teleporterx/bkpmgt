from motor.motor_asyncio import AsyncIOMotorClient

MONGO_DETAILS = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
db = client["bkpmgt_db"]
status_collection = db["client_status"]
initialized_local_repos_collection = db["initialized_local_repos"] 
initialized_s3_repos_collection = db["initialized_s3_repos"] 
local_repo_snapshots_collection = db["local_repo_snapshots"]
snapshot_contents_collection = db["snapshot_contents"]