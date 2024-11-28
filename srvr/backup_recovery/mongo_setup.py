# backup_recovery/mongo_setup.py
import os
from motor.motor_asyncio import AsyncIOMotorClient

# Get MongoDB host from environment variable, default to 'localhost' if not set
mongo_host = os.getenv('MONGO_HOST', 'localhost')

MONGO_DETAILS = f"mongodb://{mongo_host}:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
db = client["bkpmgt_db"]
status_collection = db["client_status"]
initialized_local_repos_collection = db["initialized_local_repos"] 
local_repo_snapshots_collection = db["local_repo_snapshots"]
local_repo_backups_collection = db["local_repo_backups"]
local_repo_restores_collection = db["local_repo_restores"]
initialized_s3_repos_collection = db["initialized_s3_repos"] 
s3_repo_snapshots_collection = db["s3_repo_snapshots"]
s3_repo_backups_collection = db["s3_repo_backups"]
s3_repo_restores_collection = db["s3_repo_restores"]