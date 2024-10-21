# backup_recovery/handlers.py
import asyncio
from datetime import datetime, timedelta, timezone
import logging

from .mongo_setup import (
    initialized_local_repos_collection,
    local_repo_snapshots_collection,
    local_repo_backups_collection,
    local_repo_restores_collection,
    initialized_s3_repos_collection,
    s3_repo_snapshots_collection,
    s3_repo_backups_collection,
    s3_repo_restores_collection,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# For websocket message handling
class BackupHandlers:
    def __init__(self):
        self.initialized_local_repos_collection = initialized_local_repos_collection
        self.local_repo_snapshots_collection = local_repo_snapshots_collection
        self.local_repo_backups_collection = local_repo_backups_collection
        self.local_repo_restores_collection = local_repo_restores_collection
        self.initialized_s3_repos_collection = initialized_s3_repos_collection
        self.s3_repo_snapshots_collection = s3_repo_snapshots_collection
        self.s3_repo_backups_collection = s3_repo_backups_collection
        # self.s3_repo_restores_collection = s3_repo_restores_collection
        self.dispatch_table = {
            "response_init_local_repo": self.handle_response_init_local_repo,
            "response_local_repo_snapshots": self.handle_response_local_repo_snapshots,
            "response_local_repo_backup": self.handle_response_local_repo_backup,
            "response_local_repo_restore": self.handle_response_local_repo_restore,
            "response_init_s3_repo": self.handle_response_init_s3_repo,
            "response_s3_repo_snapshots": self.handle_response_s3_repo_snapshots,
            "response_s3_repo_backup": self.handle_response_s3_repo_backup,
            # "response_s3_repo_restore": self.handle_response_s3_repo_restore,
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
            result_repo_snapshots = await self.local_repo_snapshots_collection.delete_many({"response_timestamp": {"$lt": cutoff_time}})
            # logger.info(f"Deleted {result_repo_snapshots.deleted_count} old repo snapshots.")

            # Cleanup old snapshot contents
            # result_snapshot_contents = await self.snapshot_contents_collection.delete_many({"timestamp": {"$lt": cutoff_time}})
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
        existing_document = await self.local_repo_snapshots_collection.find_one({
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
        await self.local_repo_snapshots_collection.update_one(
            {"systemUuid": system_uuid, "repo_path": repo_path},  # Query to find the document
            {"$set": document},  # Update the document with the new data
            upsert=True  # Create the document if it does not exist
        )
        
        logger.info(f"Stored repo snapshot response for {system_uuid} for repo path {repo_path}")

    async def handle_response_local_repo_backup(self, system_uuid, message):
        response_timestamp = datetime.now(timezone.utc)
        repo_path = message.get("repo_path")
        backup_output = message.get("backup_output")

        if not repo_path or not backup_output:
            logger.error("Received incomplete backup response.")
            return

        logger.info(f"Backup operation completed for repository: {repo_path}")

        # Process the backup output, which should contain the summary
        logger.info(f"Backup Summary: {backup_output}")

        # Document structure to insert/upsert
        document = {
            "systemUuid": system_uuid,
            "response_timestamp": response_timestamp,
            "repo_path": repo_path,
            "backup_output": backup_output,
        }

        try:
            # Upsert the document (insert or update)
            await self.local_repo_backups_collection.update_one(
                {"systemUuid": system_uuid, "repo_path": repo_path},
                {"$set": document},
                upsert=True
            )
            logger.info(f"Stored backup response for {system_uuid} for repo path {repo_path}")
        except Exception as e:
            logger.error(f"Error storing backup response data: {e}")

    async def handle_response_local_repo_restore(self, system_uuid, message):
        """
        Handle the response from the local repo restore operation.
        This function processes the restore output and updates the server state or logs as needed.
        """
        response_timestamp = datetime.now(timezone.utc)
        repo_path = message.get("repo_path")
        restore_output = message.get("restore_output")

        if not repo_path or not restore_output:
            logger.error("Received incomplete restore response.")
            return

        logger.info(f"Restore operation completed for repository: {repo_path}")

        # Process the restore output (which contains the summary)
        logger.info(f"Restore Summary: {restore_output}")

        # Document structure to insert/upsert
        document = {
            "systemUuid": system_uuid,
            "response_timestamp": response_timestamp,
            "repo_path": repo_path,
            "restore_output": restore_output,
        }

        try:
            # Upsert the document (insert or update)
            await self.local_repo_restores_collection.update_one(
                {"systemUuid": system_uuid, "repo_path": repo_path},
                {"$set": document},
                upsert=True
            )
            logger.info(f"Stored restore response for {system_uuid} for repo path {repo_path}")
        except Exception as e:
            logger.error(f"Error storing restore response data: {e}")

    async def handle_response_init_s3_repo(self, system_uuid, message):
        response_timestamp = datetime.now(timezone.utc)
        summary = message.get("summary", {})

        # Log or process the repo initialization as needed
        logger.info(f"S3 repo initialized : {summary}")

        # Store the repo initialization data in MongoDB
        document = {
            # "systemUuid": system_uuid, # as this function is not endpoint specific
            "response_timestamp": response_timestamp,
            "summary": summary,
        }

        # No need to check for existing records as client-side handling will ever allow only one repo to exist in absolute path
        try:
            await self.initialized_s3_repos_collection.update_one(
                # {"systemUuid": system_uuid}, # cannot use as unique identifier/filter as this function is not endpoint specific
                {"summary": document["summary"]},  # Use the summary itself as the filter
                {"$set": document},
                upsert=True
            )
            logger.info(f"Stored repo initialization data")
        except Exception as e:
            logger.error(f"Error storing repo initialization data: {e}")

    async def handle_response_s3_repo_snapshots(self, system_uuid, message):
        snapshots = message.get("snapshots", [])
        s3_url = message.get("s3_url")  # Retrieve the repo name
        response_timestamp = datetime.now(timezone.utc)  # Get current timestamp

        # Check if there's already an existing document for this repo
        existing_document = await self.local_repo_snapshots_collection.find_one({
            "s3_url": s3_url
        })

        if existing_document:
            # Compare existing snapshots with new snapshots
            if existing_document.get("snapshots") == snapshots:
                logger.info(f"No changes detected for s3 repo {s3_url}. Skipping update.")
                return  # No need to update if snapshots are the same
        
        # Document structure to insert/upsert
        document = {
            "response_timestamp": response_timestamp,
            "s3_url": s3_url,
            "snapshots": snapshots  # Directly include snapshots
        }

        try:
            # Upsert the document (insert or update)
            await self.s3_repo_snapshots_collection.update_one(
                {"s3_url": s3_url},  # Query to find the document
                {"$set": document},  # Update the document with the new data
                upsert=True  # Create the document if it does not exist
            )
            logger.info(f"Stored S3 repo snapshot response")
        except Exception as e:
            logger.error(f"Error storing repo snapshots data: {e}")

    async def handle_response_s3_repo_backup(self, system_uuid, message):
        response_timestamp = datetime.now(timezone.utc)  # Get current timestamp
        s3_url = message.get("s3_url")  # Retrieve the repo name
        backup_output = message.get("backup_output")

        if not s3_url or not backup_output:
            logger.error("Received incomplete backup response.")
            return

        # Check if there's already an existing document for this repo
        existing_document = await self.s3_repo_backups_collection.find_one({
            "systemUuid": system_uuid,
            "s3_url": s3_url
        })

        if existing_document:
            # Compare existing snapshots with new snapshots
            if existing_document.get("backup_output") == backup_output:
                logger.info(f"No changes detected for s3 repo {s3_url}. Skipping update.")
                return  # No need to update if snapshots are the same
        
        # Document structure to insert/upsert
        document = {
            "response_timestamp": response_timestamp,
            "s3_url": s3_url,
            "backup_output": backup_output  # Directly include snapshots
        }

        try:
            # Upsert the document (insert or update)
            await self.s3_repo_backups_collection.update_one(
                {"systemUuid": system_uuid, "s3_url": s3_url},
                {"$set": document},  # Update the document with the new data
                upsert=True  # Create the document if it does not exist
            )
            logger.info(f"Stored S3 repo backup response")
        except Exception as e:
            logger.error(f"Error storing repo backup data: {e}")