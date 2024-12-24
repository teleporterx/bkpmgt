InstanceId=$(aws ec2 run-instances \
    --image-id ami-0dee22c13ea7a9a67 \
    --count 1 \
    --instance-type t2.micro \
    --key-name c2_autoarch_keypair \
    --security-group-ids sg-01ece1366786722bd \
    --subnet-id subnet-02fb2be35eb0d7837 \
    --iam-instance-profile Name=EC2DescribeTagsInstanceProfile \
    --user-data file://uinit.sh \
    | grep -o '"InstanceId": "[^"]*' | cut -d '"' -f 4)

aws ec2 create-tags --resources $InstanceId --tags Key=Name,Value=bkpmgt_test

echo $InstanceId >> lastspawn_info.tmp
echo "Fetching instance public IP usng ec2 describe-instance..."
PublicIP=$(aws ec2 describe-instances --instance-ids $InstanceId --query 'Reservations[*].Instances[*].PublicIpAddress' --output text)
echo $PublicIP >> lastspawn_info.tmp
# Fetch the dmidecode UUID
echo "Fetching dmidecode UUID from instance..."
sleep 60 # time for instance creation
UUID=$(ssh -o StrictHostKeyChecking=no -i /home/teleporterx/c2_autoarch_keypair.pem ubuntu@$PublicIP "sudo cat /sys/class/dmi/id/product_uuid")
if [ $? -eq 0 ]; then
    echo "dmidecode UUID: $UUID"
    echo $UUID >> lastspawn_info.tmp
else
    echo "Failed to fetch dmidecode UUID." >> lastspawn_info.tmp
fi
echo "-x-x-" >> lastspawn_info.tmp