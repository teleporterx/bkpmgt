#!/bin/bash

# Save the current directory so we can return to it later
originalDirectory=$(pwd)

# Function to handle cleanup on exit
cleanup() {
    # Stop the Docker containers and remove them
    echo "Stopping and removing Docker containers..."
    docker-compose down

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

# Navigate to the directory where the docker-compose.yml file is located (assuming it's in the root of the repo)
cd "$(dirname "$0")"

# Start the Docker containers with docker-compose, without recreating existing ones
echo "Starting Docker containers with docker-compose..."
docker-compose up -d --no-recreate

# Wait for RabbitMQ to be healthy
echo "🐇 Waiting for RabbitMQ to initialize..."

# Check RabbitMQ health status
while ! docker inspect --format '{{.State.Health.Status}}' rabbitmq | grep -q "healthy"; do
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

# Change to the server directory
cd ./srvr/

# Run the Uvicorn server in the same terminal session
echo "🦄 Starting Uvicorn server..."
uvicorn srvr:app --host 0.0.0.0 --port 5000
