#!/bin/bash

# Save the current directory so we can return to it later
originalDirectory=$(pwd)

# Function to handle cleanup on exit
cleanup() {
    # Return to the original directory
    cd "$originalDirectory"
}

# Ensure the cleanup function runs on script exit (on SIGTERM/SIGKILL or normal exit)
trap cleanup EXIT

# Check if the virtual environment is already activated
if [ -z "$VIRTUAL_ENV" ]; then
    # Virtual environment is not active, so activate it
    source ./.venv/bin/activate  # Activate the virtual environment
else
    echo "Virtual environment is already active."
fi

# Change to the server directory
cd ./srvr/

# Run the Uvicorn server in the same terminal session
uvicorn srvr:app --host 0.0.0.0 --port 5000
