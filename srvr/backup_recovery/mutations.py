import strawberry
import json
import aio_pika
from comms import manager # imports the manager object from the main script

@strawberry.type
class BackupMutations:
    @strawberry.mutation
    async def allocate_repo_snapshot_task(
        self,
        system_uuid: str,
        repo: str,
        password: str,
    ) -> str:
        # Check if the client is connected
        if system_uuid not in manager.active_connections:
            return "Error: Client not connected"

        # Create a task message
        task_message = {
            "type": "repo_snapshots",
            "repo": repo,
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

        return f"Task allocated to retrieve snapshots for repo: {repo}"
