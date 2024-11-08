$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Write-Host "Executing build from $scriptDir"
# Get the grandparent directory (go up two levels from the script's directory)
$rootDir = Split-Path (Split-Path $scriptDir -Parent) -Parent
Write-Host "$rootDir"
$clntDir = Join-Path $rootDir "clnt"
Write-Host "$clntDir"

# Navigate to the clnt directory
Set-Location -Path $clntDir
# Ensure PyInstaller is available
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Warning "Enable (.venv) and make sure pyinstaller is installed"
    Set-Location -Path $scriptDir # Reset Path
    exit
}

# Define the paths to the directories (relative to the current working directory)
$resticExe = Join-Path $clntDir "restic.exe"
$staticDir = Join-Path $clntDir "static"

# Check if the "restic" directory exists
if (-not (Test-Path $resticExe)) {
    Write-Warning "The 'restic' directory does not exist. Please ensure it's present in $clntDir."
    exit  # Stop execution if restic is missing
}

# Check if the "static" directory exists
if (-not (Test-Path $staticDir)) {
    Write-Warning "The 'static' directory does not exist. Please ensure it's present in $clntDir."
    exit  # Stop execution if static is missing
}

# If all checks pass, run pyinstaller
Write-Host "Bundling client..."
pyinstaller --onefile --add-data "restic.exe:." --add-data "static:static" clnt.py

# Navigate to the installer directory
$installerDir = Join-Path $rootDir "installer"
Set-Location -Path $installerDir
Write-Host "Changed directory to installer: $installerDir"

# Ensure that the clnt.exe and wazuh-agent.msi exist
$clntExe = Join-Path $clntDir "dist\clnt.exe"
$wazuhMsi = Join-Path $installerDir "wazuh-agent.msi"
$nssmExe = Join-Path $installerDir "nssm.exe"

if (-not (Test-Path $clntExe)) {
    Write-Warning "clnt.exe not found in dist/ directory. Ensure the build was successful."
    exit
}

if (-not (Test-Path $wazuhMsi)) {
    Write-Warning "wazuh-agent.msi not found in installer/ directory. Ensure it's present."
    exit
}

# Run pyinstaller again to bundle the installer script
Write-Host "Bundling installer..."
pyinstaller --onefile --add-data "$($nssmExe):." --add-data "$($clntExe):." --add-data "$($wazuhMsi):." deepsec_installer.py

Set-Location -Path $rootDir

Write-Host "Build complete!"