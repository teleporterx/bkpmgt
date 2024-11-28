# backup_recovery/mutations.py
import strawberry
import json
import aio_pika
from srvr.comms import manager # imports the manager object from the main script
from srvr.backup_recovery.s3_helper import s3_restic_helper
import logging
from typing import List, Optional
from datetime import datetime, timezone
from srvr.backup_recovery.mut_validations import *
# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mutations for task allocation
@strawberry.type
class BackupMutations:
    # Granular time duration model
    @strawberry.input
    class TimeDurationInput:
        # Include relevant time denominations, rule out un-realistic ones {months, years, ...}
        days: int = 0
        hours: int = 0
        minutes: int = 0
        seconds: int = 0

    @strawberry.mutation
    async def init_local_repo(
        self,
        system_uuid: str,
        repo_path: str,
        password: str,
        command_history: Optional[bool] = None,
    ) -> str:
        # Check if the client is connected
        if system_uuid not in manager.active_connections:
            return "Error: Client not connected"

        # Create a task message for initializing the repository
        task_message = {
            "type": "init_local_repo",
            "repo_path": repo_path,
            "password": password,
            "command_history": command_history,
        }

        # no scheduling stuff as it's a one-time configuration task, and scheduling it doesn’t add much value.

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
        command_history: Optional[bool] = None,
        scheduler: Optional[str] = None,
        scheduler_priority: Optional[int] = None,
        interval: Optional[TimeDurationInput] = None,
        timelapse: Optional[str] = None,  # date-time string; ISO 8601 format
        scheduler_repeats: Optional[str] = None
    ) -> str:
        
        # Check if the client is connected
        if system_uuid not in manager.active_connections:
            return "Error: Client not connected"

        task_map = { # if scheduler is specified
            # Need input validation in later stages (this is just a proto)
            "interval": "schedule_interval_get_local_repo_snapshots",
            "timelapse": "schedule_timelapse_get_local_repo_snapshots",
        }
        # if scheduler is specified, use the corresponding task
        task_type = task_map.get(scheduler, "get_local_repo_snapshots")
        
        # Create a task message for initializing the repository
        task_message = {
            "type": task_type,
            "repo_path": repo_path,
            "password": password,
            "command_history": command_history,
        }

        """
        Retrieving or listing snapshots could be useful for auditing purposes, reporting, or triggering notifications when new snapshots are available. Scheduling could make sense here if you need periodic checks or periodic reports of snapshot status.
        """

        if scheduler:
            scheduler_repeats_validation = validate_scheduler_repeats(scheduler_repeats)
            scheduler_priority_validation = validate_scheduler_priority(scheduler_priority)
            # If either validation fails, return the respective error message
            if scheduler_repeats_validation and "Error" in scheduler_repeats_validation:
                return "Error: Invalid scheduler_repeats input!"  # Return the error for scheduler_repeats
            
            if scheduler_priority_validation and "Error" in scheduler_priority_validation:
                return "Error: Invalid scheduler_priority input!"  # Return the error for scheduler_priority
            
            # Proceed with valid values
            task_message["scheduler_repeats"] = scheduler_repeats_validation
            task_message["scheduler_priority"] = scheduler_priority_validation

            # task_message updates for scheduler types
            scheduling_action = {
                "interval": lambda: task_message.update({
                    "interval": {
                        "days": interval.days,
                        "hours": interval.hours,
                        "minutes": interval.minutes,
                        "seconds": interval.seconds,
                    }
                }) if interval else None,
                "timelapse": lambda: task_message.update({
                    "timelapse": datetime.fromisoformat(timelapse).astimezone(timezone.utc).isoformat() if timelapse else None
                }) if timelapse else None
            }
            try:
                action = scheduling_action[scheduler]
                action() # Execute the action for the corresponding type of scheduler
            except KeyError as e:
                return f"Error: Invalid scheduler {e}"

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
        command_history: Optional[bool] = None,
        exclude: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        custom_options: Optional[List[str]] = None,
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
            "command_history": command_history,
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
        command_history: Optional[bool] = None,
        exclude: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        custom_options: Optional[List[str]] = None,
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
            "command_history": command_history,
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
        org: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region: str,
        bucket_name: str,
        password: str,
        aws_session_token: Optional[str] = None,
    ) -> str:
        
        try:
            result = await s3_restic_helper(
                aws_access_key_id, 
                aws_secret_access_key, 
                region, 
                bucket_name, 
                password, 
                aws_session_token,
                org,
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
        aws_session_token: Optional[str] = None,
    ) -> str:

        try:
            result = await s3_restic_helper(
                aws_access_key_id, 
                aws_secret_access_key, 
                region, 
                bucket_name, 
                password, 
                aws_session_token,
                "", 
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
        command_history: Optional[bool] = None,
        exclude: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        custom_options: Optional[List[str]] = None,
        aws_session_token: Optional[str] = None,
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
            "command_history": command_history,
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
        command_history: Optional[bool] = None,
        exclude: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        custom_options: Optional[List[str]] = None,
        aws_session_token: Optional[str] = None,
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
            "command_history": command_history,
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