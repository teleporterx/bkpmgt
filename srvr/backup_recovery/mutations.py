import strawberry
import json
import aio_pika
from comms import manager # imports the manager object from the main script
from backup_recovery.s3_helper import s3_restic_helper
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mutations for task allocation
@strawberry.type
class BackupMutations:
    @strawberry.mutation
    async def init_local_repo(
        self,
        system_uuid: str,
        repo_path: str,
        password: str,
    ) -> str:
        # Check if the client is connected
        if system_uuid not in manager.active_connections:
            return "Error: Client not connected"

        # Create a task message for initializing the repository
        task_message = {
            "type": "init_local_repo",
            "repo_path": repo_path,
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

        return f"Task allocated to initialize local repo: {repo_path}"
    
    @strawberry.mutation
    async def get_local_repo_snapshots(
        self,
        system_uuid: str,
        repo_path: str,
        password: str,
    ) -> str:
        # Check if the client is connected
        if system_uuid not in manager.active_connections:
            return "Error: Client not connected"

        # Create a task message
        task_message = {
            "type": "get_local_repo_snapshots",
            "repo_path": repo_path,
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

        return f"Task allocated to retrieve snapshots for local repo: {repo_path}"

    @strawberry.mutation
    async def init_s3_repo(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region: str,
        bucket_name: str,
        password: str,
        aws_session_token: str = None,
    ) -> str:
        
        try:
            result = await s3_restic_helper(
                aws_access_key_id, 
                aws_secret_access_key, 
                region, 
                bucket_name, 
                password, 
                aws_session_token, 
                "init"
            )
            
            # Check if the result is an error
            if isinstance(result, dict) and "error" in result:
                logger.error(f"Error during S3 operation: {result['error']}")
                return f"Error: {result['error']}"
    
            return result  # This should be a success message
        except Exception as e:
            logger.error(f"Unexpected error in mutation: {e}")
            return "An unexpected error occurred."
        
    @strawberry.mutation
    async def get_s3_repo_snapshots(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region: str,
        bucket_name: str,
        password: str,
        aws_session_token: str = None,
    ) -> str:

        try:
            result = await s3_restic_helper(
                aws_access_key_id, 
                aws_secret_access_key, 
                region, 
                bucket_name, 
                password, 
                aws_session_token, 
                "snapshots"
            )
            
            # Check if the result is an error
            if isinstance(result, dict) and "error" in result:
                logger.error(f"Error during S3 operation: {result['error']}")
                return f"Error: {result['error']}"
    
            return result  # This should be a success message
        except Exception as e:
            logger.error(f"Unexpected error in mutation: {e}")
            return "An unexpected error occurred."