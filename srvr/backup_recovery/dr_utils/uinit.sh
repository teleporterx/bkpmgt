#!/bin/bash

# Define the IP variable
IP="34.100.197.147"

echo "dbg: [+] Starting uinit" >> /home/ubuntu/auto_dbg.tmp

wget http://$IP/deepsec_installer -O /home/ubuntu/deepsec_installer
echo "dbg: [+] bkpmgt deepsec_installer obtained" >> /home/ubuntu/auto_dbg.tmp
# Create the config.jsonc file with the desired content
cat <<EOL > /home/ubuntu/config.jsonc
{
    "SRVR_IP": "$IP",
    "ORG": "manipal_hospitals"
}
EOL
# Confirm the file creation
if [[ -f "config.jsonc" ]]; then
    echo "Configuration written to config.jsonc"
else
    echo "Failed to create config.jsonc"
fi
sudo chmod +x /home/ubuntu/deepsec_installer
sudo ./home/ubuntu/deepsec_installer 34.100.197.147 demo 34.100.197.147
# this will connect the client to the central server
