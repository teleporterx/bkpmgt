# Save the current directory so we can return to it later
$originalDirectory = Get-Location

try {
    # Check if the virtual environment is already activated
    if (-not $env:VIRTUAL_ENV) {
        # Virtual environment is not active, so activate it
        .\.venv\Scripts\Activate.ps1  # Activate the virtual environment
    } else {
        Write-Host "Virtual environment is already active."
    }

    Set-Location -Path .\srvr\  # Change to the server directory

    # Run the Uvicorn server in the same CLI session
    uvicorn srvr:app --host 0.0.0.0 --port 5000
}
finally {
    # Return to the original directory when the script ends (on SIGTERM/SIGKILL or normal exit)
    Set-Location -Path $originalDirectory
}
