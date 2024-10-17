import boto3 # aws SDK for Python for S3 stuff
import botocore # for exception handling
import logging
import subprocess
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def s3_restic_funcs(aws_access_key_id, aws_secret_access_key, region, bucket_name, password, aws_session_token, func_type):

    if not aws_access_key_id or not aws_secret_access_key or not region or not bucket_name or not password:
        return {"error": "Missing essential initialization data!"}
    
    # Create a new session with the specified credentials
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token  # Include session token if provided
    )

    # Create an S3 resource with the specified region
    s3 = session.resource('s3', region_name=region)

    # Initialize a flag to determine if the bucket exists
    bucket_exists = False

    try:
        # Check if the bucket exists
        s3.meta.client.head_bucket(Bucket=bucket_name)
        logger.info(f"Bucket {bucket_name} already exists.")
        bucket_exists = True
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            if func_type == "init":
                # Bucket does not exist, so create it
                logger.info(f"Bucket {bucket_name} does not exist. Creating it...")
                s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={
                    'LocationConstraint': region
                })
                logger.info(f"Bucket {bucket_name} created successfully.")
                bucket_exists = True
            else:
                logger.error(f"Bucket {bucket_name} does not exist and cannot be created for {func_type} operation.")
                return {"error": f"Bucket {bucket_name} does not exist."}
        elif e.response['Error']['Code'] == 'InvalidAccessKeyId':
            logger.error("Invalid AWS Access Key ID provided.")
            return {"error": "Invalid AWS Access Key ID."}
        else:
            logger.error(f"Failed to access bucket: {e}")
            return {"error": str(e)}

    # Construct RESTIC_REPOSITORY from attrs.
    restic_repo = f"s3:s3.{region}.amazonaws.com/{bucket_name}"

    try:
        # Check if the bucket exists before executing snapshots
        if func_type == "snapshots" and not bucket_exists:
            return {"error": f"Bucket {bucket_name} does not exist. Cannot perform snapshots."}

        # Set environment variables using env as a dict
        env = os.environ.copy()  # Copy existing environment variables
        env.update({
            'AWS_ACCESS_KEY_ID': aws_access_key_id,
            'AWS_SECRET_ACCESS_KEY': aws_secret_access_key,
            'AWS_SESSION_TOKEN': aws_session_token if aws_session_token else '',
            'RESTIC_REPOSITORY': restic_repo,
            'RESTIC_PASSWORD': password
        })

        # Determine the command based on func_type
        if func_type == "init":
            command = ['./backup_recovery/restic', 'init', '--json']
        elif func_type == "snapshots":
            command = ['./backup_recovery/restic', 'snapshots', '--json']
        else:
            return {"error": f"Unsupported func_type: {func_type}"}

        result = subprocess.run(command, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            if "repository master key and config already initialized" in result.stderr and func_type == "init":
                logger.info(f"Repository at {restic_repo} already initialized.")
                return f"Repository at {restic_repo} already initialized."
            logger.error(f"Command failed with return code {result.returncode}: {result.stderr}")
            return f"Command failed: {result.stderr}"

        logger.info(f"Successfully executed {func_type} operation at {restic_repo}")
        return f"Successfully executed {func_type} operation at {restic_repo}"
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run command: {e}")
        return {"error": f"Failed to run command: {e}"}
    except subprocess.TimeoutExpired:
        logger.error("Timeout while executing the command.")
        return {"error": "Timeout while executing the command"}
    except botocore.exceptions.ClientError as e:
        logger.error(f"Client error occurred: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Failed to execute operation: {e}")
        return {"error": str(e)}