import strawberry
import json
import aio_pika
from comms import manager # imports the manager object from the main script
from backup_recovery.s3_helper import s3_restic_helper
import logging
from typing import List

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
    async def do_local_repo_backup(
        self,
        system_uuid: str,
        repo_path: str,
        password: str,
        paths: List[str],
        exclude: List[str] = None,
        tags: List[str] = None,
        custom_options: List[str] = None,
    ) -> str:
        # Check if the client is connected
        if system_uuid not in manager.active_connections:
            return "Error: Client not connected"
        
        # Validation for input data goes here

        # Create a task message for backup
        task_message = {
            "type": "do_local_repo_backup",
            "repo_path": repo_path,
            "password": password,
            "paths": paths,
            "exclude": exclude or [],
            "tags": tags or [],
            "custom_options": custom_options or [],
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

        return f"Task allocated to backup to local repo: {repo_path}"
    
    @strawberry.mutation
    async def do_local_repo_restore(
        self,
        system_uuid: str,
        repo_path: str,
        password: str,
        snapshot_id: str,
        target_path: str,
        exclude: List[str] = None,
        include: List[str] = None,
        custom_options: List[str] = None,
    ) -> str:
        # Check if the client is connected
        if system_uuid not in manager.active_connections:
            return "Error: Client not connected"
        
        # Create a task message for restore
        task_message = {
            "type": "do_local_repo_restore",
            "repo_path": repo_path,
            "password": password,
            "snapshot_id": snapshot_id,
            "target_path": target_path,
            "exclude": exclude or [],
            "include": include or [],
            "custom_options": custom_options or [],
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

        return f"Task allocated to restore from local repo: {repo_path}"

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
        
    @strawberry.mutation
    async def do_s3_repo_backup(
        self,
        system_uuid: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region: str,
        bucket_name: str,
        password: str,
        paths: List[str],
        exclude: List[str] = None,
        tags: List[str] = None,
        custom_options: List[str] = None,
        aws_session_token: str = None,
    ) -> str:
        # Check if the client is connected
        if system_uuid not in manager.active_connections:
            return "Error: Client not connected"
        
        # Validation for input data goes here

        # Create a task message for backup
        task_message = {
            "type": "do_s3_repo_backup",
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
            "aws_session_token": aws_session_token,
            "region": region,
            "bucket_name": bucket_name,
            "password": password,
            "paths": paths,
            "exclude": exclude or [],
            "tags": tags or [],
            "custom_options": custom_options or [],
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

        return f"Task allocated to backup to s3 repo: {bucket_name}"

    @strawberry.mutation
    async def do_s3_repo_restore(
        self,
        system_uuid: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region: str,
        bucket_name: str,
        password: str,
        snapshot_id: str,
        target_path: str,
        exclude: List[str] = None,
        include: List[str] = None,
        custom_options: List[str] = None,
        aws_session_token: str = None,
    ) -> str:
        # Check if the client is connected
        if system_uuid not in manager.active_connections:
            return "Error: Client not connected"

        # Create a task message for restore
        task_message = {
            "type": "do_s3_repo_restore",
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
            "aws_session_token": aws_session_token,
            "region": region,
            "bucket_name": bucket_name,
            "password": password,
            "snapshot_id": snapshot_id,
            "target_path": target_path,
            "exclude": exclude or [],
            "include": include or [],
            "custom_options": custom_options or [],
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

        return f"Task allocated to restore from s3 repo: {bucket_name}"