# Determine the script directory and root directory
scriptDir="$(dirname "$(realpath "$0")")"
echo "Executing build from $scriptDir"

# Get the grandparent directory (go up two levels from the script's directory)
rootDir="$(dirname "$(dirname "$scriptDir")")"
echo "Root directory: $rootDir"

clntDir="$rootDir/clnt"
echo "Client directory: $clntDir"

# Navigate to the clnt directory
cd "$clntDir" || { echo "Failed to navigate to $clntDir"; exit 1; }

# Ensure PyInstaller is available
if ! command -v pyinstaller &>/dev/null; then
    echo "Warning: PyInstaller not found. Ensure you're in the virtual environment and PyInstaller is installed."
    cd "$scriptDir"  # Reset back to the original script directory
    exit 1
fi

# Define the paths to the directories (relative to the current working directory)
resticElf="$clntDir/restic"
staticDir="$clntDir/static"

# Check if the "restic" ELF file exists
if [ ! -f "$resticElf" ]; then
    echo "Warning: The 'restic' ELF file does not exist. Please ensure it's present in $clntDir."
    exit 1
fi

# Check if the "static" directory exists
if [ ! -d "$staticDir" ]; then
    echo "Warning: The 'static' directory does not exist. Please ensure it's present in $clntDir."
    exit 1
fi

# If all checks pass, run pyinstaller to bundle the client
echo "Bundling client..."
pyinstaller --onefile --add-data "$resticElf:." --add-data "$staticDir:static" clnt.py

# Navigate to the installer directory
installerDir="$rootDir/installer"
cd "$installerDir" || { echo "Failed to navigate to $installerDir"; exit 1; }
echo "Changed directory to installer: $installerDir"

# Ensure that the client ELF and wazuh-agent.msi exist
clntElf="$clntDir/dist/clnt"
wazuhDeb="$installerDir/wazuh-agent"

if [ ! -f "$clntElf" ]; then
    echo "Warning: $clntElf not found in dist/ directory. Ensure the build was successful."
    exit 1
fi

if [ ! -f "$wazuhDeb" ]; then
    echo "Warning: $wazuhDeb not found in installer/ directory. Ensure it's present."
    exit 1
fi

# Run pyinstaller again to bundle the installer script
echo "Bundling installer..."
pyinstaller --onefile --add-data "$clntElf:." --add-data "$wazuhDeb:." deepsec_installer.py