import platform
import sys
import argparse
import os
import subprocess
import shutil
import json
from uuid_info import get_system_uuid

def get_resource_path(filename):
    """Return the resource path depending on if we are bundled or running as a script."""
    if getattr(sys, 'frozen', False):
        # Running from a bundled executable
        base_path = sys._MEIPASS
    else:
        # Running as a script
        base_path = os.path.dirname(__file__)

    return os.path.join(base_path, filename)

def create_config(config_params, target_dir):
    """Create config.jsonc file with given parameters in the target directory."""
    config_path = os.path.join(target_dir, 'config.jsonc')

    config = {
        "SRVR_IP": config_params.get('bkpmgt_srvr_ip'),
        "ORG": config_params.get('group_name')
    }

    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"Config file {config_path} created successfully.")
    except Exception as e:
        print(f"Error creating config file: {e}")
        sys.exit(1)

# Function to extract and place the Wazuh MSI (Windows)
def extract_msi_windows(wazuh_msi_path, target_dir):
    """Extract and place the wazuh-agent.msi into the target directory on Windows."""
    try:
        # Ensure target directory exists
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        # Extract and copy the MSI file to the target directory
        shutil.copy(wazuh_msi_path, target_dir)
        print(f"Wazuh MSI extracted to {target_dir}")
    except Exception as e:
        print(f"Error extracting wazuh MSI: {e}")
        sys.exit(1)

# Function to install Wazuh agent (Windows)
def install_wazuh_agent_windows(wazuh_msi_path, wazuh_manager, agent_name, group_name):
    """Install Wazuh agent on Windows using msiexec."""
    command = f"msiexec /i \"{wazuh_msi_path}\" WAZUH_MANAGER=\"{wazuh_manager}\" WAZUH_AGENT_GROUP=\"{group_name}\" WAZUH_AGENT_NAME=\"{agent_name}\" /quiet"
    try:
        print(f"Running command: {command}")
        # Use shell=True to execute the command as a string
        subprocess.run(command, check=True, shell=True)
        print("Wazuh agent installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing Wazuh agent: {e}")
        sys.exit(1)

# Function to extract and place the clnt binary (Windows)
def extract_clnt_windows(clnt_path, nssm_path):
    """Extract and place clnt.exe in Program Files on Windows."""
    target_dir = r"C:\Program Files\DeepDefend"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    try:
        shutil.copy(clnt_path, target_dir)
        print(f"clnt.exe extracted to {target_dir}")
        shutil.copy(nssm_path, target_dir)
        print(f"nssm.exe extracted to {target_dir}")
    except Exception as e:
        print(f"Error extracting clnt.exe: {e}")
        sys.exit(1)

# Function to create Windows service for clnt.exe
def create_windows_service(nssm_path, install_dir):
    """Create a Windows service to run the clnt binary."""
    service_name = "deepdefend"
    try:
        command = [
            nssm_path, "install", service_name, f"{install_dir}"
        ]
        subprocess.run(command, check=True)
        print(f"Windows service '{service_name}' created successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error creating Windows service: {e}")
        sys.exit(1)

# Function to install Wazuh agent (Linux)
def install_wazuh_agent_linux(wazuh_msi_path, wazuh_manager, agent_name, group_name):
    """Install Wazuh agent on Linux using dpkg."""
    command = [
        'sudo', 'WAZUH_MANAGER=' + wazuh_manager,
        'WAZUH_AGENT_GROUP=' + group_name,
        'WAZUH_AGENT_NAME=' + agent_name,
        'dpkg', '-i', str(wazuh_msi_path),
    ]
    try:
        print(f"Running command: {' '.join(command)}")
        subprocess.run(command, check=True)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["sudo", "systemctl", "enable", "wazuh-agent"], check=True)
        subprocess.run(["sudo", "systemctl", "start", "wazuh-agent"], check=True)
        print("Wazuh agent installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing Wazuh agent: {e}")
        sys.exit(1)

# Function to extract and place the clnt binary (Linux)
def extract_clnt_linux(clnt_path):
    """Extract and place clnt in /opt/DeepDefend on Linux."""
    target_dir = "/opt/DeepDefend"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    try:
        shutil.copy(clnt_path, target_dir)
        print(f"clnt binary extracted to {target_dir}")
    except Exception as e:
        print(f"Error extracting clnt: {e}")
        sys.exit(1)

# Function to create Linux systemd service for clnt binary
def create_linux_service(clnt_path):
    """Create a systemd service to run the clnt binary on Linux."""
    service_name = "deepdefend.service"
    service_path = f"/etc/systemd/system/{service_name}"
    
    service_unit = f"""
    [Unit]
    Description=DeepDefend Service
    After=network.target
    
    [Service]
    ExecStart={clnt_path}
    WorkingDirectory=/opt/DeepDefend
    Restart=always
    User=root
    
    [Install]
    WantedBy=multi-user.target
    """

    try:
        with open(service_path, "w") as f:
            f.write(service_unit)

        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["sudo", "systemctl", "enable", "deepdefend.service"], check=True)
        subprocess.run(["sudo", "systemctl", "start", "deepdefend.service"], check=True)
        print("Linux service created and started successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error creating Linux service: {e}")
        sys.exit(1)

def main():
    # idea: this data can be loaded from a CONFIG file
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Install and configure DeepDefend.")
    parser.add_argument('xdr_srvr_ip', type=str, help='IP address of the xdr server.')
    # parser.add_argument('agent_name', type=str, help='Name for the agent.')
    parser.add_argument('group_name', type=str, help='Agent group')
    parser.add_argument('bkpmgt_srvr_ip', type=str, help='IP address of bkpmgt server')

    args = parser.parse_args()

    # Get the Wazuh Manager and Agent Name from command-line arguments
    wazuh_manager = args.xdr_srvr_ip
    agent_name = get_system_uuid()
    group_name = args.group_name

    platform_type = platform.system()

    # Get the resource paths for the binaries
    wazuh_msi_path = get_resource_path("wazuh-agent.msi") if platform_type == "Windows" else get_resource_path("wazuh-agent.deb")
    clnt_path = get_resource_path("clnt.exe" if platform_type == "Windows" else "clnt")
    
    if platform_type == "Windows":
        # locate the bundled nssm installer
        nssm_path = get_resource_path("nssm.exe")
        target_dir = r'C:\Program Files\DeepDefend'  # Set target directory
        # Extract the MSI to the DeepDefend directory
        extract_msi_windows(wazuh_msi_path, target_dir)
        install_wazuh_agent_windows(os.path.join(target_dir, "wazuh-agent.msi"), wazuh_manager, agent_name, group_name)
        extract_clnt_windows(clnt_path, nssm_path)
        # Create config file in the target directory based on arguments
        create_config(vars(args), target_dir)
        create_windows_service(os.path.join(target_dir, "nssm.exe"), os.path.join(target_dir, "clnt.exe"))

    elif platform_type == "Linux":
        target_dir = r'/opt/DeepDefend'  # Set target directory
        install_wazuh_agent_linux(wazuh_msi_path, wazuh_manager, agent_name, group_name)
        extract_clnt_linux(clnt_path)
        # Create config file in the target directory based on arguments
        create_config(vars(args), target_dir)
        create_linux_service(f"/opt/DeepDefend/{os.path.basename(clnt_path)}")
    
    # elif platform_type == "Darwin":  # macOS
    #     install_wazuh_agent_macos(wazuh_msi_path, wazuh_manager, agent_name)
    #     extract_clnt_macos(clnt_path)
    #     create_macos_service(f"/Applications/DeepDefend/{os.path.basename(clnt_path)}")

    else:
        print("Unsupported platform.")
        sys.exit(1)

if __name__ == "__main__":
    main()