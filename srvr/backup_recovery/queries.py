# backup_recovery/queries.py
import strawberry
from typing import List, Optional

from srvr.backup_recovery.mongo_setup import (
    initialized_local_repos_collection,
    initialized_s3_repos_collection,
)

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
