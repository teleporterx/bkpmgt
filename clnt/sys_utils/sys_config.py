import os
import sys
import commentjson

# Get the directory where the executable is located
BIN_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

# Construct the full path to the config file
CONFIG_FILE_PATH = os.path.join(BIN_DIR, "config.jsonc")

def load_config():
    """
    Load the configuration from the JSONC file.
    """
    if not os.path.exists(CONFIG_FILE_PATH):
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_FILE_PATH}")
    
    with open(CONFIG_FILE_PATH, 'r') as f:
        config = commentjson.load(f)
    return config