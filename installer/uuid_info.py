import platform
import subprocess

def get_system_uuid_linux():
    try:
        result = subprocess.check_output(['sudo', 'dmidecode', '-s', 'system-uuid']).decode().strip()
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving system UUID on Linux: {e.output.decode()}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_system_uuid_windows():
    try:
        result = subprocess.check_output(
            ['powershell', '-Command', '(Get-WmiObject -Class Win32_ComputerSystemProduct).UUID']
        ).decode().strip()
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving system UUID on Windows: {e.output.decode()}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_system_uuid_mac():
    try:
        result = subprocess.check_output(
            "ioreg -rd1 -c IOPlatformExpertDevice | grep IOPlatformUUID",
            shell=True).decode()
        uuid = result.split('"')[-2]
        return uuid
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving system UUID on MacOS: {e.output.decode()}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_system_uuid():
    os_name = platform.system()

    if os_name == "Linux":
        return get_system_uuid_linux()
    elif os_name == "Windows":
        return get_system_uuid_windows()
    elif os_name == "Darwin":  # MacOS
        return get_system_uuid_mac()
    else:
        print(f"Unsupported OS: {os_name}")
        return None