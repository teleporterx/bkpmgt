# backup_utils/schedule_manager.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from backup_utils import handlers

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
    
    async def schedule_task(self, message_data, handler, scheduling_type):
        """
        Schedules a task based on the message data and directly calls the regular handler.
        """
        # Decide which handler to call based on the message type
        if scheduling_type == "interval":
            interval = message_data.get("interval")
            # Schedule the task based on the interval
            self.scheduler.add_job(handler, 'interval', **interval, args=[message_data])
            logger.info(f"Scheduled some task: with interval: {interval}")
        elif scheduling_type == "timelapse":
            timelapse = message_data.get("timelapse")
            # Schedule the task based on the timelapse
            # self.scheduler.add_job(handler, 'date', run_date=timelapse, args=[message_data, websocket])
            logger.info(f"Scheduled some task: with timelapse: {timelapse}")
        else:
            logger.error(f"No interval or timelapse found for scheduling task <some task>")
            return

    def list_jobs(self):
        """
        Lists all scheduled jobs along with the operation being performed.
        """
        jobs = self.scheduler.get_jobs()
        if jobs:
            logger.info("Listing all scheduled jobs:")
            for job in jobs:
                # Try to get the job's handler function name or description
                handler_name = job.func.__name__ if hasattr(job.func, '__name__') else str(job.func)
                logger.info(f"Job ID: {job.id}, Next run time: {job.next_run_time}, Operation: {handler_name}")
        else:
            logger.info("No jobs are currently scheduled.")

    def delete_job(self, job_id):
        """
        Deletes a specific job by its ID.
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Job with ID {job_id} has been removed.")
        except Exception as e:
            logger.error(f"Error removing job with ID {job_id}: {e}")

    def delete_all_jobs(self):
        """
        Deletes all scheduled jobs.
        """
        self.scheduler.remove_all_jobs()
        logger.info("All jobs have been removed.")