from srvr.comms import manager # imports the manager object from the main script
import aio_pika
import json

async def get_q(system_uuid):
    queue = manager.queues.get(system_uuid)
    if not queue:
        raise ValueError("Queue not found for the client")
    return queue

async def pub_msg(task_message, queue):
    await manager.channel.default_exchange.publish(
        aio_pika.Message(body=json.dumps(task_message).encode()),
        routing_key=queue.name  # Use the name of the queue as the routing key
    )