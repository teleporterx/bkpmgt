# backup_recovery/mutations.py
import strawberry
from srvr.comms import manager # imports the manager object from the main script
from srvr.backup_recovery.s3_helper import s3_restic_helper
import logging
from typing import List, Optional
from datetime import datetime, timezone
from srvr.backup_recovery.mut_validations import *
from srvr.comms import rmq_manager
from srvr.backup_recovery.models import TimeDurationInput
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
        command_history: Optional[bool] = None,
    ) -> str:
        # Check if the client is connected
        if not await manager.check_conn(system_uuid):
            return "Error: Client not connected"

        # Create a task message for initializing the repository
        task_message = {
            "type": "init_local_repo",
            "repo_path": repo_path,
            "password": password,
            "command_history": command_history,
        }

        # no scheduling stuff as it's a one-time configuration task, and scheduling it doesn’t add much value.

        try:
            # Get the client's queue
            queue = await rmq_manager.get_q(system_uuid)
        
            # Publish the task to the client's queue
            await rmq_manager.pub_msg(task_message, queue)
        
        except ValueError as e:
            print(f"Error: {e}")

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
        if not await manager.check_conn(system_uuid):
            return "Error: Client not connected"

        task_type = "schedule_get_local_repo_snapshots" if scheduler else "get_local_repo_snapshots"
        
        # Create a task message
        task_message = {
            "type": task_type,
            "repo_path": repo_path,
            "password": password,
            "command_history": command_history,
        }

        """
        Retrieving or listing snapshots could be useful for auditing purposes, reporting, or triggering notifications when new snapshots are available. Scheduling could make sense here if you need periodic checks or periodic reports of snapshot status.
        """

        # Call the helper function to handle scheduler
        scheduler_error = prime_scheduler(
            scheduler, scheduler_repeats, scheduler_priority, interval, timelapse, task_message
        )
        
        if scheduler_error:
            return scheduler_error  # Return the error if something went wrong with scheduler handling

        try:
            # Get the client's queue
            queue = await rmq_manager.get_q(system_uuid)
        
            # Publish the task to the client's queue
            await rmq_manager.pub_msg(task_message, queue)
        
        except ValueError as e:
            print(f"Error: {e}")

        return f"Task allocated to retrieve snapshots for local repo: {repo_path}"

    # Do local repo backup
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
        scheduler: Optional[str] = None,
        scheduler_repeats: Optional[str] = None,
        scheduler_priority: Optional[int] = None,
        interval: Optional[TimeDurationInput] = None,
        timelapse: Optional[str] = None,
    ) -> str:
        # Check if the client is connected
        if not await manager.check_conn(system_uuid):
            return "Error: Client not connected"
        
        task_type = "schedule_do_local_repo_backup" if scheduler else "do_local_repo_backup"

        # Create a task message for backup
        task_message = {
            "type": task_type,
            "repo_path": repo_path,
            "password": password,
            "paths": paths,
            "exclude": exclude or [],
            "tags": tags or [],
            "custom_options": custom_options or [],
            "command_history": command_history,
        }

        # Call the helper function to handle scheduler
        scheduler_error = prime_scheduler(
            scheduler, scheduler_repeats, scheduler_priority, interval, timelapse, task_message
        )
        
        if scheduler_error:
            return scheduler_error  # Return the error if something went wrong with scheduler handling

        try:
            # Get the client's queue
            queue = await rmq_manager.get_q(system_uuid)
        
            # Publish the task to the client's queue
            await rmq_manager.pub_msg(task_message, queue)
        
        except ValueError as e:
            print(f"Error: {e}")

        return f"Task allocated to backup to local repo: {repo_path}"
    
    # Do local repo restore
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
        scheduler: Optional[str] = None,
        scheduler_repeats: Optional[str] = None,
        scheduler_priority: Optional[int] = None,
        interval: Optional[TimeDurationInput] = None,
        timelapse: Optional[str] = None,
    ) -> str:
        # Check if the client is connected
        if not await manager.check_conn(system_uuid):
            return "Error: Client not connected"
        
        task_type = "schedule_do_local_repo_restore" if scheduler else "do_local_repo_restore"

        # Create a task message for restore
        task_message = {
            "type": task_type,
            "repo_path": repo_path,
            "password": password,
            "snapshot_id": snapshot_id,
            "target_path": target_path,
            "exclude": exclude or [],
            "include": include or [],
            "custom_options": custom_options or [],
            "command_history": command_history,
        }

        # Call the helper function to handle scheduler
        scheduler_error = prime_scheduler(
            scheduler, scheduler_repeats, scheduler_priority, interval, timelapse, task_message
        )
        
        if scheduler_error:
            return scheduler_error  # Return the error if something went wrong with scheduler handling

        try:
            # Get the client's queue
            queue = await rmq_manager.get_q(system_uuid)
        
            # Publish the task to the client's queue
            await rmq_manager.pub_msg(task_message, queue)
        
        except ValueError as e:
            print(f"Error: {e}")

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
        scheduler: Optional[str] = None,
        scheduler_repeats: Optional[str] = None,
        scheduler_priority: Optional[int] = None,
        interval: Optional[TimeDurationInput] = None,
        timelapse: Optional[str] = None,
    ) -> str:
        # Check if the client is connected
        if not await manager.check_conn(system_uuid):
            return "Error: Client not connected"
        
        task_type = "schedule_do_s3_repo_backup" if scheduler else "do_s3_repo_backup"

        # Validation for input data goes here

        # Create a task message for backup
        task_message = {
            "type": task_type,
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

        # Call the helper function to handle scheduler
        scheduler_error = prime_scheduler(
            scheduler, scheduler_repeats, scheduler_priority, interval, timelapse, task_message
        )
        
        if scheduler_error:
            return scheduler_error  # Return the error if something went wrong with scheduler handling

        try:
            # Get the client's queue
            queue = await rmq_manager.get_q(system_uuid)
        
            # Publish the task to the client's queue
            await rmq_manager.pub_msg(task_message, queue)
        
        except ValueError as e:
            print(f"Error: {e}")

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
        scheduler: Optional[str] = None,
        scheduler_repeats: Optional[str] = None,
        scheduler_priority: Optional[int] = None,
        interval: Optional[TimeDurationInput] = None,
        timelapse: Optional[str] = None,
    ) -> str:
        # Check if the client is connected
        if not await manager.check_conn(system_uuid):
            return "Error: Client not connected"

        task_type = "schedule_do_local_repo_restore" if scheduler else "do_local_repo_restore"

        # Create a task message for restore
        task_message = {
            "type": task_type,
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

        # Call the helper function to handle scheduler
        scheduler_error = prime_scheduler(
            scheduler, scheduler_repeats, scheduler_priority, interval, timelapse, task_message
        )
        
        if scheduler_error:
            return scheduler_error  # Return the error if something went wrong with scheduler handling

        try:
            # Get the client's queue
            queue = await rmq_manager.get_q(system_uuid)

            # Publish the task to the client's queue
            await rmq_manager.pub_msg(task_message, queue)

        except ValueError as e:
            print(f"Error: {e}")

        return f"Task allocated to restore from s3 repo: {bucket_name}"