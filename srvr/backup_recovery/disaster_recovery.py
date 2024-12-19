import logging
import os
import datetime
import asyncio
from typing import Dict
import json5  # Use json5 for parsing JSONC files

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DRMonitor:
    def __init__(self, config_file: str, conn_manager):
        self.config = self.load_config(config_file)
        self.agent_status = {}  # Track agent connection times
        self.conn_manager = conn_manager  # Pass ConnectionManager instance for access to connection status

        # Filter agents from the DR configuration that are enabled
        self.enabled_agents = self.get_enabled_agents()

        # Listen for connection and disconnection updates from ConnectionManager
        self.conn_manager.on_connect = self.handle_connect
        self.conn_manager.on_disconnect = self.handle_disconnect

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

    def get_enabled_agents(self):
        """Get the list of agents that are enabled in the DR configuration."""
        enabled_agents = {}

        # Iterate over organizations
        for org, org_data in self.config["ORGS"].items():
            dr_config = org_data.get("DR", {})
            if not dr_config:
                print(f"DR configuration missing for organization: {org}")
                continue

            agents = dr_config.get("agents", {})
            if not agents:
                print(f"No agents found for organization: {org}")
                continue

            # Iterate through the agents for each organization
            for agent_uuid, agent_info in agents.items():
                print(f"Found agent {agent_uuid}: {agent_info}")

                # Ensure it's enabled
                if isinstance(agent_info, dict) and agent_info.get("enabled", False):
                    enabled_agents[agent_uuid] = agent_info
                    print(f"Agent {agent_uuid} is enabled, adding to enabled_agents.")
                else:
                    print(f"Agent {agent_uuid} is either not a dictionary or not enabled.")

        # Return the dictionary of enabled agents
        print(f"Enabled agents after processing: {list(enabled_agents.keys())}")
        return enabled_agents

    async def monitor_disconnects(self):
        """Monitor the disconnect status of each agent periodically."""
        logger.info("DRMonitor initialized!")
        while True:
            current_time = datetime.datetime.now()

            for org, org_data in self.config["ORGS"].items():
                dr_config = org_data.get("DR", {})
                if not dr_config:
                    continue  # Skip if DR configuration is missing

                for agent_uuid, agent_info in dr_config["agents"].items():
                    if agent_uuid not in self.enabled_agents:
                        continue  # Skip disabled agents
                    
                    last_connected_time = self.agent_status.get(agent_uuid)

                    if last_connected_time is None:
                        logger.info(f"Agent {agent_uuid} is currently disconnected.")
                        continue  # Skip if agent is disconnected

                    # Calculate time difference
                    time_diff = current_time - last_connected_time
                    threshold = self.parse_duration(agent_info["DR_monitoring_threshold"])

                    if time_diff > threshold:
                        logger.warning(f"Agent {agent_uuid} disconnected for {time_diff}, exceeding threshold!")
                        logger.info(f"Triggering restore for agent {agent_uuid} with config: {agent_info['restore_config']}")
                        self.trigger_restore(agent_info["restore_config"])

            # Polling interval
            await asyncio.sleep(60)  # Wait before checking again

    def parse_duration(self, duration_str: str) -> datetime.timedelta:
        """Parse a human-readable duration string into a timedelta object."""
        try:
            if duration_str.startswith("PT"):
                # Extract hours and minutes, account for optional zero values
                hours = 0
                minutes = 0
                
                # Parse the hours if it exists
                if 'H' in duration_str:
                    hours_part = duration_str.split('H')[0][2:]  # Get value after "PT"
                    if hours_part:
                        hours = int(hours_part)
                
                # Parse the minutes if it exists
                if 'M' in duration_str:
                    minutes_part = duration_str.split('M')[0].split('H')[-1]  # Get value after "H"
                    if minutes_part:
                        minutes = int(minutes_part)
                logger.info(f"Parsed duration for '{duration_str}': {hours} hours, {minutes} minutes")
                return datetime.timedelta(hours=hours, minutes=minutes)
        
            # Allow more flexible formats like "1h30m" or "1h 30m"
            hours, minutes = 0, 0
            if 'h' in duration_str:
                hours = int(duration_str.split('h')[0])
            if 'm' in duration_str:
                minutes = int(duration_str.split('m')[0].split()[-1])
    
            return datetime.timedelta(hours=hours, minutes=minutes)
        
        except ValueError as e:
            logger.error(f"Error parsing duration: {e}")
            return datetime.timedelta()  # Default duration in case of error

    def trigger_restore(self, restore_config: Dict):
        """Trigger the restore operation."""
        logger.info(f"Triggering restore with config: {restore_config}")
        #AWS CLI spinup with source agent config
        # Implement your restore logic here
        # E.g., restore from a backup system, trigger API call, etc.

    async def handle_connect(self, system_uuid: str):
        """Handle agent connection event."""
        # Log the received UUID and the list of enabled agents
        logger.info(f"Received connection from agent: {system_uuid}")
        logger.info(f"Enabled agents: {list(self.enabled_agents.keys())}")

        # Update the agent's connection time
        if system_uuid in self.enabled_agents:  # Only track enabled agents
            self.agent_status[system_uuid] = datetime.datetime.now()  # Record the time of connection
            logger.info(f"Agent {system_uuid} connected at {self.agent_status[system_uuid]}")
        else:
            logger.info(f"Agent {system_uuid} is not enabled or not in the DR configuration. Skipping.")

    async def handle_disconnect(self, system_uuid: str):
        """Handle agent disconnection event."""
        if system_uuid not in self.enabled_agents:
            logger.info(f"Agent {system_uuid} is not in the DR configuration or not enabled. Skipping.")
            return

        if system_uuid in self.agent_status:
            # Log disconnection time
            logger.info(f"Agent {system_uuid} disconnected at {datetime.datetime.now()}.")
            # Do not remove from tracking; keep last connected time for monitoring
            # Optionally, you could set a flag or status to indicate disconnection
        else:
            logger.warning(f"Agent {system_uuid} was not found in agent status tracking.")
