# Define function to perform cleanup
cleanup() {
    local directory="$1"

    # Check if the directory exists
    if [ -d "$directory" ]; then
        echo "Cleaning up $directory"

        # Remove dist, build, and .spec files/folders
        rm -rf "$directory/dist" "$directory/build" "$directory"/*.spec 2>/dev/null
    else
        echo "Warning: Directory $directory not found, skipping cleanup."
    fi
}

# Define directories
scriptDir="$(dirname "$(realpath "$0")")"
rootDir="$(dirname "$(dirname "$scriptDir")")"
clntDir="$rootDir/clnt"
installerDir="$rootDir/installer"

# Perform cleanup on clnt and installer directories
cleanup "$clntDir"
cleanup "$installerDir"

echo "Cleanup complete... Build files removed!"
