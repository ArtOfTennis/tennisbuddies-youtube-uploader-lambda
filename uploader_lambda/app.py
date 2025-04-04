import json
import boto3
import os
import mimetypes

# import requests


def lambda_handler(event, context):
    """Lambda function that downloads an S3 object and returns file type and size
    
    Parameters
    ----------
    event: dict, required
        Input event data with s3_key
    
    context: object, required
        Lambda Context runtime methods and attributes
    
    Returns
    ------
    dict: Object information including fileType and fileSize
    """
    
    # Get the S3 key from the event
    s3_key = event.get('s3_key')
    
    if not s3_key:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Missing required parameter: s3_key"
            }),
        }
    
    # Initialize S3 client
    s3 = boto3.client('s3')
    bucket_name = os.environ.get('S3_BUCKET_NAME')
    
    try:
        # Get object metadata
        response = s3.head_object(Bucket=bucket_name, Key=s3_key)
        file_size = response['ContentLength']
        
        # Create temp directory if it doesn't exist
        temp_dir = '/tmp/downloads'
        os.makedirs(temp_dir, exist_ok=True)
        
        # Download the file
        local_file_path = f'{temp_dir}/{os.path.basename(s3_key)}'
        s3.download_file(bucket_name, s3_key, local_file_path)
        
        # Determine file type
        file_type, _ = mimetypes.guess_type(local_file_path)
        if not file_type:
            file_type = 'application/octet-stream'
        
        # Log the information
        print(f"Downloaded {s3_key} from {bucket_name}")
        print(f"File Type: {file_type}")
        print(f"File Size: {file_size} bytes")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "s3_key": s3_key,
                "fileType": file_type,
                "fileSize": file_size
            }),
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            }),
        }
