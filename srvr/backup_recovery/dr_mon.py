import logging
import os
import json5
import asyncio
from dateutil.parser import isoparse
from datetime import datetime, timedelta

# MongoDB setup
from srvr.backup_recovery.mongo_setup import status_collection

# Setup logging
logging.basicConfig(level=logging.DEBUG)  # Change to DEBUG to see debug logs
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class DRMonitor:
    def __init__(self, config_file: str):
        self.config = self.load_config(config_file)
        if not self.config:
            logger.error("Failed to load DR configuration. Exiting monitor.")
            return
        self.status_collection = status_collection
        self.monitor_task = None

    def load_config(self, config_file: str) -> dict:
        """Load disaster recovery configuration from a JSONC file using json5."""
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"{config_file} not found.")
        
        try:
            with open(config_file, 'r') as file:
                config = json5.load(file)
        except json5.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSONC from {config_file}: {e}")
        
        return config

    def parse_duration(self, duration_str: str) -> timedelta:
        """Parse an ISO 8601 duration string (e.g., PT1H30M) into a timedelta object."""
        hours = 0
        minutes = 0
        seconds = 0
        if "H" in duration_str:
            hours = int(duration_str.split("H")[0].replace("PT", ""))
            duration_str = duration_str.split("H")[1]
        if "M" in duration_str:
            minutes = int(duration_str.split("M")[0])
        return timedelta(hours=hours, minutes=minutes, seconds=seconds)

    async def check_dr_clients(self):
        logger.debug("Checking DR Clients..")
        for org_name, org_data in self.config.get("ORGS", {}).items():
            if "DR" in org_data:
                for agent_uuid, agent_config in org_data["DR"]["agents"].items():
                    if agent_config.get("enabled"):
                        logger.debug(f"Checking DR client for agent {agent_uuid} in {org_name}")

                        # Check the status in MongoDB
                        try:
                            status_doc = await status_collection.find_one({"system_uuid": agent_uuid})
                            if not status_doc:
                                logger.debug(f"No status found for agent {agent_uuid} in {org_name}")
                                continue
                            
                            connected_at = status_doc.get("connected_at")
                            disconnected_at = status_doc.get("last_disconnected")

                            if connected_at is None or disconnected_at is None:
                                logger.warning(f"Missing timestamps for agent {agent_uuid} in {org_name}")
                                continue

                            # Check if disconnected_at is already a datetime object
                            if isinstance(disconnected_at, str):
                                logger.debug(f"disconnected_at value before parsing: {disconnected_at}")
                                disconnected_at = isoparse(disconnected_at)
                            elif isinstance(disconnected_at, datetime):
                                logger.debug(f"disconnected_at value is already a datetime object: {disconnected_at}")
                            else:
                                logger.warning(f"Unexpected format for disconnected_at: {disconnected_at}")
                                continue

                            # Calculate the time difference from the current time
                            current_time = datetime.utcnow()  # Get the current time (UTC)
                            logger.debug(f"disconnected_at: {disconnected_at}, current_time: {current_time}")

                            time_diff = current_time - disconnected_at
                            logger.debug(f"Current time: {current_time}, time_diff: {time_diff}")

                            # Parse the DR monitoring threshold
                            threshold = agent_config.get("DR_monitoring_threshold")
                            if threshold:
                                try:
                                    threshold_time = self.parse_duration(threshold)
                                    logger.debug(f"Threshold time: {threshold_time}")

                                    if time_diff > threshold_time:
                                        logger.warning(f"Agent {agent_uuid} in {org_name} has been disconnected for too long!")
                                        # Take necessary action (e.g., send alert or trigger recovery process)
                                         # Call the trigger_restore function to start the restore process
                                        await self.trigger_restore(org_name, agent_uuid, agent_config)
                                except ValueError:
                                    logger.error(f"Invalid threshold format for {agent_uuid} in {org_name}: {threshold}")
                        except Exception as e:
                            logger.error(f"Error checking DR client for agent {agent_uuid} in {org_name}: {e}")

    async def trigger_restore(self, org_name: str, agent_uuid: str, agent_config: dict):
        """Trigger restore operation for the agent that has exceeded the threshold."""
        logger.info(f"Triggering restore for agent {agent_uuid} in {org_name}")

        # Retrieve the restore configuration for the agent
        restore_config = agent_config.get("restore_config")
        if not restore_config:
            logger.error(f"Restore configuration missing for agent {agent_uuid} in {org_name}")
            return

        # Log the restore configuration details (could be passed to a restore service or API)
        logger.info(f"Restore configuration for agent {agent_uuid}: {restore_config}")

        # Simulate the restore process (this is where you'd call the actual restore logic)
        # For now, just log the success of the operation
        try:
            # This is where the restore logic would occur (e.g., call a backup/restore API)
            logger.info(f"Restore initiated for agent {agent_uuid} in {org_name} using config: {restore_config}")

            # Example: Assuming restore is successful
            logger.info(f"Restore completed for agent {agent_uuid} in {org_name}")
        except Exception as e:
            logger.error(f"Error during restore for agent {agent_uuid} in {org_name}: {e}")

    async def monitor_dr_status(self):
        """Monitor the DR status in a loop with periodic checks."""
        # PATCH: You may need to change this value later depending on agent's exponential backoff
        await asyncio.sleep(60)  # Wait for a minute to allow agents to connect
        while True:
            logger.debug("Starting the DR monitoring loop...")
            await self.check_dr_clients()  # Check connection statuses
            logger.debug("Completed checking DR clients. Waiting for next iteration.")
            await asyncio.sleep(60)  # Wait for a minute before rechecking

    async def start_monitoring(self):
        """Start monitoring as an async task directly."""
        logger.debug("Started DR Monitoring")
        try:
            await self.monitor_dr_status()
        except Exception as e:
            logger.error(f"Error starting DR Monitoring: {e}")