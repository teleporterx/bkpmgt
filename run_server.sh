#!/bin/bash

# Save the current directory so we can return to it later
originalDirectory=$(pwd)

# Function to handle cleanup on exit
cleanup() {
    # Stop the Docker containers and remove them
    echo "Stopping and removing Docker containers..."
    sudo docker-compose down

    # Return to the original directory
    cd "$originalDirectory"
}

# Ensure the cleanup function runs on script exit (on SIGTERM/SIGKILL or normal exit)
trap cleanup EXIT

# Dynamically get the current user's home directory
USER_HOME=$(eval echo ~$USER)

# Ensure magic is available for sudo by explicitly adding its path to the sudo environment
export PATH=$PATH:$USER_HOME/.modular/bin

# Navigate to the directory where the docker-compose.yml file is located (assuming it's in the root of the repo)
cd "$(dirname "$0")"

# Check if Docker daemon is running by testing the connection to the Docker socket
if ! sudo docker info > /dev/null 2>&1; then
    echo "❌ Cannot connect to the Docker daemon. Is the Docker daemon running?"
    exit 1
fi

# Start the Docker containers with docker-compose, without recreating existing ones
echo "Starting Docker containers with docker-compose..."
sudo docker-compose up -d --no-recreate

# Wait for RabbitMQ to be healthy
echo "🐇 Waiting for RabbitMQ to initialize..."

# Check RabbitMQ health status
while ! sudo docker inspect --format '{{.State.Health.Status}}' rabbitmq | grep -q "healthy"; do
    echo "🥕 Waiting for RabbitMQ to become healthy..."
    sleep 2
done

echo "🐰 RabbitMQ is now healthy!"

# Check if MongoDB is ready
check_container_ready() {
    local container_name=$1
    local port=$2
    # Wait until the container's port is accessible
    while ! nc -z localhost $port; do
        echo "Waiting for $container_name to be available on port $port..."
        sleep 2
    done
    echo "$container_name is up and running!"
}

# Check if MongoDB is ready
check_container_ready "🍃 MongoDB" 27017

# After Docker is up and RabbitMQ & MongoDB are ready, proceed with virtual environment activation

# Check if the .magic directory exists
if [ -d ".magic" ]; then
    # .magic directory exists, use magic shell to activate the environment
    echo "🪄 Using magic..."
    echo "🦄 Starting Uvicorn server..."
    # Instead of running `magic shell`, we use `magic run` to continue the script and run Uvicorn
    cd ./srvr/
    magic run uvicorn srvr:app --host 0.0.0.0 --port 5000
else
    # .magic directory does not exist, fall back to .venv
    if [ -z "$VIRTUAL_ENV" ]; then
        # Virtual environment is not active, so activate it
        source ./.venv/bin/activate  # Activate the virtual environment
    else
        echo "Virtual environment is already active."
    fi

    # Run the Uvicorn server in the same terminal session
    echo "🦄 Starting Uvicorn server..."
    cd ./srvr/
    uvicorn srvr:app --host 0.0.0.0 --port 5000
fi