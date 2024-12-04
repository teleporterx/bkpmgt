# Save the current directory so we can return to it later
$originalDirectory = Get-Location

try {
    # Ensure the cleanup function runs on script exit (on SIGTERM/SIGKILL or normal exit)
    $cleanup = {
        Write-Host "Stopping and removing Docker containers..."
        docker-compose down

        # Return to the original directory
        Set-Location -Path $originalDirectory
    }
    # Register cleanup function to be called on script exit
    $null = Register-EngineEvent -SourceIdentifier "PowerShell.Exiting" -Action $cleanup

    # Check if the virtual environment is already activated
    if (-not $env:VIRTUAL_ENV) {
        # Virtual environment is not active, so activate it
        .\.venv\Scripts\Activate.ps1  # Activate the virtual environment
    } else {
        Write-Host "Virtual environment is already active."
    }

    # Navigate to the directory where the docker-compose.yml file is located (assuming it's in the root of the repo)
    Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Definition)

    # Start the Docker containers with docker-compose, without recreating existing ones
    Write-Host "Starting Docker containers with docker-compose..."
    docker-compose up -d --no-recreate

    # Wait for RabbitMQ to be healthy
    Write-Host "🐇 Waiting for RabbitMQ to initialize..."

    # Check RabbitMQ health status
    while ($true) {
        $rabbitmqHealth = docker inspect --format '{{.State.Health.Status}}' rabbitmq
        if ($rabbitmqHealth -eq "healthy") {
            Write-Host "🐰 RabbitMQ is now healthy!"
            break
        }
        Write-Host "🥕 Waiting for RabbitMQ to become healthy..."
        Start-Sleep -Seconds 2
    }

    # Function to check if a container is ready by verifying its port is open
    function Check-ContainerReady {
        param(
            [string]$containerName,
            [int]$port
        )
        while ($true) {
            try {
                $tcpConnection = Test-NetConnection -ComputerName "localhost" -Port $port
                if ($tcpConnection.TcpTestSucceeded) {
                    Write-Host "$containerName is up and running!"
                    break
                }
            } catch {
                Write-Host "Waiting for $containerName to be available on port $port..."
            }
            Start-Sleep -Seconds 2
        }
    }

    # Check if MongoDB is ready
    Check-ContainerReady -containerName "🍃 MongoDB" -port 27017

    # Change to the server directory
    # Set-Location -Path .\srvr\

    # Run the Uvicorn server in the same terminal session
    Write-Host "🦄 Starting Uvicorn server..."
    uvicorn srvr.srvr:app --host 0.0.0.0 --port 5000
}
finally {
    # Clean up and return to the original directory when the script ends
    Set-Location -Path $originalDirectory
}