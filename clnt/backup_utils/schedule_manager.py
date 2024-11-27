import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScheduleManager:
    def __init__(self, db_path="bkpmgt.db"):
        # Set up the APScheduler with SQLite as the job store
        self.scheduler = AsyncIOScheduler(jobstores={
            'default': SQLAlchemyJobStore(url=f"sqlite:///{db_path}")  # Store jobs in the existing SQLite DB
        })
        self.scheduler.start()

        self.dispatch_table = {
            "schedule_interval_get_local_repo_snapshots": handle_interval_timelapse_get_local_repo_snapshots,
            "schedule_timelapse_get_local_repo_snapshots": handle_schedule_timelapse_get_local_repo_snapshots,
        }
    
    async def handle_scheduled_task(self, message_data, websocket):
        """
        Handles scheduled tasks (interval or timelapse).
        """
        message_type = message_data.get("type")
        handler = self.dispatch_table.get(message_type)

        if handler:
            # Call the appropriate handler
            await handler(message_data, websocket)
        else:
            logger.warning(f"Unknown scheduled message type: {message_type}")

async def handle_interval_timelapse_get_local_repo_snapshots(params, websocket):
    logger.info(f"get local repo snapshots is being handled")
    pass

async def handle_schedule_timelapse_get_local_repo_snapshots(params, websocket):
    logger.info(f"get local repo snapshots is being handled")
    pass