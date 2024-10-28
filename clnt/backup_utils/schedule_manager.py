import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_dummy(params, websocket):
    logger.info(f"dummy is being handled")
    pass

dispatch_table = {
    "schedule_interval_init_local_repo": handle_dummy,
    # "schedule_interval": handle_schedule_interval,
    # "schedule_timelapse": handle_schedule_timelapse,
}

async def task_scheduler(message_data, websocket):
    message_type = message_data.get("type")
    handler = dispatch_table.get(message_type)

    if handler:
        await handler(message_data, websocket)
    else:
        logger.warning(f"Unknown scheduled message type: {message_type}")