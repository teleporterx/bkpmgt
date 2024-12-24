#!/bin/bash

echo "dbg: [+] Starting uinit" >> /home/admin/auto_dbg.tmp

wget http://43.204.144.143:1414/clnt -O /home/admin/clnt
echo "dbg: [+] bkpmgt clnt obtained" >> /home/admin/auto_dbg.tmp
# Create the config.jsonc file with the desired content
cat <<EOL > /home/admin/config.jsonc
{
    "SRVR_IP": "localhost",
    "ORG": "manipal_hospitals"
}
EOL
# Confirm the file creation
if [[ -f "config.jsonc" ]]; then
    echo "Configuration written to config.jsonc"
else
    echo "Failed to create config.jsonc"
fi
sudo chmod +x /home/admin/clnt
sudo ./home/admin/clnt # this will connect the client to the central server
