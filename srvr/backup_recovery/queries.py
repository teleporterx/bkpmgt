# backup_recovery/queries.py
import strawberry
from typing import List, Optional

from srvr.backup_recovery.mongo_setup import (
    initialized_local_repos_collection,
    initialized_s3_repos_collection,
    local_repo_snapshots_collection,
    s3_repo_snapshots_collection,
    local_repo_backups_collection,
    s3_repo_backups_collection,
    local_repo_restores_collection,
    s3_repo_restores_collection
)

# Define the RestoreOutput type (maps the structure of the restore_output field)
@strawberry.type
class RestoreOutput:
    message_type: Optional[str]
    total_files: Optional[int]
    files_restored: Optional[int]
    total_bytes: Optional[int]
    bytes_restored: Optional[int]

# Define the RestoreJob type
@strawberry.type
class RestoreJob:
    task_uuid: Optional[str]
    restore_output: Optional[RestoreOutput]
    org: Optional[str]
    repo_path: Optional[str]
    response_timestamp: Optional[str]
    system_uuid: Optional[str]
    task_status: Optional[str]
    s3_url: Optional[str]  # S3-specific field

# Define the BackupOutput type (maps the structure of the backup_output field)
@strawberry.type
class BackupOutput:
    message_type: Optional[str]
    files_new: Optional[int]
    files_changed: Optional[int]
    files_unmodified: Optional[int]
    dirs_new: Optional[int]
    dirs_changed: Optional[int]
    dirs_unmodified: Optional[int]
    data_blobs: Optional[int]
    tree_blobs: Optional[int]
    data_added: Optional[int]
    data_added_packed: Optional[int]
    total_files_processed: Optional[int]
    total_bytes_processed: Optional[int]
    total_duration: Optional[float]
    snapshot_id: Optional[str]

# Define the BackupJob type
@strawberry.type
class BackupJob:
    task_uuid: Optional[str]
    backup_output: Optional[BackupOutput]
    org: Optional[str]
    repo_path: Optional[str]
    response_timestamp: Optional[str]
    system_uuid: Optional[str]
    task_status: Optional[str]
    s3_url: Optional[str]  # S3-specific field

# Define the Summary type (mapping fields from the summary dictionary)
@strawberry.type
class Summary:
    backup_start: Optional[str]
    backup_end: Optional[str]
    files_new: Optional[int]
    files_changed: Optional[int]
    files_unmodified: Optional[int]
    dirs_new: Optional[int]
    dirs_changed: Optional[int]
    dirs_unmodified: Optional[int]
    data_blobs: Optional[int]
    tree_blobs: Optional[int]
    data_added: Optional[int]
    data_added_packed: Optional[int]
    total_files_processed: Optional[int]
    total_bytes_processed: Optional[int]

# Define the Snapshot type (updated to use Summary)
@strawberry.type
class Snapshot:
    system_uuid: Optional[str]
    org: Optional[str]
    type: Optional[str]
    repo_path: Optional[str]
    s3_url: Optional[str]
    snapshot_id: Optional[str]
    short_id: Optional[str]
    time: Optional[str]
    tree: Optional[str]
    paths: Optional[List[str]]
    hostname: Optional[str]
    username: Optional[str]
    program_version: Optional[str]
    summary: Optional[Summary]  # Use the new Summary type

# Define the InitializedRepo type
@strawberry.type
class InitializedRepo:
    system_uuid: Optional[str]
    org: Optional[str]
    type: Optional[str]
    repo: Optional[str]
    id: Optional[str]

# Queries for info retrieval
@strawberry.type
class BackupQueries:
    @strawberry.field
    async def get_initialized_repos(
        self,
        system_uuid: Optional[str] = None,
        org: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[InitializedRepo]:
        # Validate `type` and determine collections to query
        if type == "local":
            collections = [initialized_local_repos_collection]
        elif type == "s3":
            collections = [initialized_s3_repos_collection]
        else:
            collections = [initialized_local_repos_collection, initialized_s3_repos_collection]

        repos = []
        for collection in collections:
            # Build filters dynamically based on inputs
            filters = {}
            if system_uuid:
                filters["systemUuid"] = system_uuid
            if org:
                filters["org"] = org

            # Query the collection and iterate asynchronously
            async for repo in collection.find(filters):
                repos.append(
                    InitializedRepo(
                        system_uuid=repo.get("systemUuid"),
                        # Fetch `org` from the document, if available, instead of relying on query input
                        org=repo.get("org"),
                        type="local" if collection == initialized_local_repos_collection else "s3",
                        repo=repo["summary"]["repository"],
                        id=repo["summary"]["id"],
                    )
                )
        return repos

    @strawberry.field
    async def get_repo_snapshots(
        self,
        system_uuid: Optional[str] = None,
        org: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[Snapshot]:
        # Validate `type` and determine collections to query
        if type == "local":
            collections = [local_repo_snapshots_collection]
        elif type == "s3":
            collections = [s3_repo_snapshots_collection]
        else:
            collections = [local_repo_snapshots_collection, s3_repo_snapshots_collection]

        snapshots = []
        for collection in collections:
            # Build filters dynamically based on inputs
            filters = {}
            if system_uuid and collection == local_repo_snapshots_collection:
                filters["systemUuid"] = system_uuid  # Only filter by systemUuid for local snapshots
            if org:
                filters["org"] = org

            # Query the collection and iterate asynchronously
            async for snapshot_doc in collection.find(filters):
                # For S3 snapshots, we iterate through the snapshots array
                for snapshot in snapshot_doc.get('snapshots', []):
                    # Map the summary field to the new Summary type
                    summary_data = snapshot.get('summary', {})
                    summary = Summary(
                        backup_start=summary_data.get('backup_start'),
                        backup_end=summary_data.get('backup_end'),
                        files_new=summary_data.get('files_new'),
                        files_changed=summary_data.get('files_changed'),
                        files_unmodified=summary_data.get('files_unmodified'),
                        dirs_new=summary_data.get('dirs_new'),
                        dirs_changed=summary_data.get('dirs_changed'),
                        dirs_unmodified=summary_data.get('dirs_unmodified'),
                        data_blobs=summary_data.get('data_blobs'),
                        tree_blobs=summary_data.get('tree_blobs'),
                        data_added=summary_data.get('data_added'),
                        data_added_packed=summary_data.get('data_added_packed'),
                        total_files_processed=summary_data.get('total_files_processed'),
                        total_bytes_processed=summary_data.get('total_bytes_processed')
                    )

                    snapshots.append(
                        Snapshot(
                            system_uuid=snapshot_doc.get("systemUuid") if collection == local_repo_snapshots_collection else None,
                            org=snapshot_doc.get("org"),
                            type="local" if collection == local_repo_snapshots_collection else "s3",
                            snapshot_id=snapshot.get('id'),
                            time=snapshot.get('time'),
                            tree=snapshot.get('tree'),
                            paths=snapshot.get('paths'),
                            hostname=snapshot.get('hostname'),
                            username=snapshot.get('username'),
                            program_version=snapshot.get('program_version'),
                            short_id=snapshot.get('short_id'),
                            summary=summary,
                            repo_path=snapshot_doc.get("repo_path"),  # Add repo_path
                            s3_url=snapshot_doc.get("s3_url")  # Add s3_url
                        )
                    )
        return snapshots

    @strawberry.field
    async def get_backup_jobs(
        self,
        system_uuid: Optional[str] = None,
        org: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[BackupJob]:
        # Determine which collections to query based on the `type`
        if type == "local":
            collections = [local_repo_backups_collection]
        elif type == "s3":
            collections = [s3_repo_backups_collection]
        else:
            collections = [local_repo_backups_collection, s3_repo_backups_collection]
    
        backup_jobs = []
    
        # Loop through the collections and fetch documents
        for collection in collections:
            filters = {}
            if system_uuid:
                filters["systemUuid"] = system_uuid
            if org:
                filters["org"] = org
    
            # Query the collection and iterate over the documents asynchronously
            async for backup_job_doc in collection.find(filters):
                # Ensure that backup_output_data is a dictionary or empty dictionary if None
                backup_output_data = backup_job_doc.get("backup_output", {})
                if backup_output_data is None:
                    backup_output_data = {}
    
                # Map the backup_output field to the new BackupOutput type
                backup_output = BackupOutput(
                    message_type=backup_output_data.get('message_type'),
                    files_new=backup_output_data.get('files_new'),
                    files_changed=backup_output_data.get('files_changed'),
                    files_unmodified=backup_output_data.get('files_unmodified'),
                    dirs_new=backup_output_data.get('dirs_new'),
                    dirs_changed=backup_output_data.get('dirs_changed'),
                    dirs_unmodified=backup_output_data.get('dirs_unmodified'),
                    data_blobs=backup_output_data.get('data_blobs'),
                    tree_blobs=backup_output_data.get('tree_blobs'),
                    data_added=backup_output_data.get('data_added'),
                    data_added_packed=backup_output_data.get('data_added_packed'),
                    total_files_processed=backup_output_data.get('total_files_processed'),
                    total_bytes_processed=backup_output_data.get('total_bytes_processed'),
                    total_duration=backup_output_data.get('total_duration'),
                    snapshot_id=backup_output_data.get('snapshot_id')
                )
    
                # Append the BackupJob to the result list
                backup_jobs.append(
                    BackupJob(
                        task_uuid=backup_job_doc.get("task_uuid"),
                        backup_output=backup_output,
                        org=backup_job_doc.get("org"),
                        repo_path=backup_job_doc.get("repo_path"),
                        response_timestamp=str(backup_job_doc.get("response_timestamp")),
                        system_uuid=backup_job_doc.get("systemUuid"),
                        task_status=backup_job_doc.get("task_status"),
                        s3_url=backup_job_doc.get("s3_url")  # S3-specific field
                    )
                )
    
        return backup_jobs

    @strawberry.field
    async def get_restore_jobs(
        self,
        system_uuid: Optional[str] = None,
        org: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[RestoreJob]:
        # Determine which collections to query based on the `type`
        if type == "local":
            collections = [local_repo_restores_collection]
        elif type == "s3":
            collections = [s3_repo_restores_collection]
        else:
            collections = [local_repo_restores_collection, s3_repo_restores_collection]

        restore_jobs = []

        # Loop through the collections and fetch documents
        for collection in collections:
            filters = {}
            if system_uuid:
                filters["systemUuid"] = system_uuid
            if org:
                filters["org"] = org

            # Query the collection and iterate over the documents asynchronously
            async for restore_job_doc in collection.find(filters):
                # Retrieve restore_output, it might be a string or dictionary
                restore_output_data = restore_job_doc.get("restore_output", {})

                # If restore_output is a string (empty or otherwise), set it to an empty dictionary
                if isinstance(restore_output_data, str):
                    restore_output_data = {}

                # Map the restore_output field to the RestoreOutput type
                restore_output = RestoreOutput(
                    message_type=restore_output_data.get('message_type'),
                    total_files=restore_output_data.get('total_files'),
                    files_restored=restore_output_data.get('files_restored'),
                    total_bytes=restore_output_data.get('total_bytes'),
                    bytes_restored=restore_output_data.get('bytes_restored')
                )

                # Append the RestoreJob to the result list
                restore_jobs.append(
                    RestoreJob(
                        task_uuid=restore_job_doc.get("task_uuid"),
                        restore_output=restore_output,
                        org=restore_job_doc.get("org"),
                        repo_path=restore_job_doc.get("repo_path"),
                        response_timestamp=str(restore_job_doc.get("response_timestamp")),
                        system_uuid=restore_job_doc.get("systemUuid"),
                        task_status=restore_job_doc.get("task_status"),
                        s3_url=restore_job_doc.get("s3_url")  # S3-specific field
                    )
                )

        return restore_jobs