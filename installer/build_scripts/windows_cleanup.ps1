# Define function to perform cleanup
function Cleanup {
    param (
        [string]$directory
    )
    
    # Check if the directory exists
    if (Test-Path $directory) {
        Write-Host "Cleaning up $directory"
        
        # Remove the dist, build, and .spec files/folders
        Remove-Item -Path (Join-Path $directory "dist") -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -Path (Join-Path $directory "build") -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -Path (Join-Path $directory "*.spec") -Force -ErrorAction SilentlyContinue
    } else {
        Write-Warning "Directory $directory not found, skipping cleanup."
    }
}

# Define directories
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$rootDir = Split-Path (Split-Path $scriptDir -Parent) -Parent
$clntDir = Join-Path $rootDir "clnt"
$installerDir = Join-Path $rootDir "installer"

# Perform cleanup on clnt and installer directories
Cleanup -directory $clntDir
Cleanup -directory $installerDir

Write-Host "Cleanup complete... Build files removed!"
