# backup_recovery/queries.py
import strawberry
from typing import List, Optional

from srvr.backup_recovery.mongo_setup import (
    initialized_local_repos_collection,
    initialized_s3_repos_collection,
    local_repo_snapshots_collection,
    s3_repo_snapshots_collection
)

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
                            summary=summary
                        )
                    )
        return snapshots