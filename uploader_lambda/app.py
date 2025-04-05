import json
import boto3
import os
import mimetypes
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# YouTube API constants
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]


def get_authenticated_service():
    """
    Get authenticated YouTube service using credentials from AWS Secrets Manager
    """
    try:
        # Get AWS region from environment variable with fallback to us-west-1
        aws_region = os.environ.get('AWS_SECRETS_MANAGER_REGION', 'us-west-1')
        
        # Initialize AWS Secrets Manager client
        secrets_client = boto3.client('secretsmanager', region_name=aws_region)
        
        # Get secret ID from environment variable
        secret_id = os.environ.get('YOUTUBE_API_SECRET_ID')
        if not secret_id:
            raise Exception("YOUTUBE_API_SECRET_ID environment variable not set")
        
        # Get secret from AWS Secrets Manager
        response = secrets_client.get_secret_value(SecretId=secret_id)
        secret = json.loads(response['SecretString'])
        
        # Extract credentials from secret
        token = secret.get("TOKEN")
        refresh_token = secret.get("REFRESH_TOKEN")
        token_uri = secret.get("TOKEN_URI")
        client_id = secret.get("CLIENT_ID")
        client_secret = secret.get("CLIENT_SECRET")
        
        if not all([token, refresh_token, token_uri, client_id, client_secret]):
            raise Exception("Missing credential fields in secret")
        
        # Create credentials object
        creds = Credentials(
            token=token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=[YOUTUBE_UPLOAD_SCOPE]
        )
        
        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            
            # Update secret with new token
            secret["TOKEN"] = creds.token
            secrets_client.put_secret_value(
                SecretId=secret_id,
                SecretString=json.dumps(secret)
            )
        
        if not creds or not creds.valid:
            raise Exception("Invalid credentials")
            
        return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=creds)
        
    except Exception as e:
        print(f"Error in authentication: {e}")
        raise


def get_webhook_secret():
    """
    Get webhook authentication details from AWS Secrets Manager
    """
    try:
        # Get AWS region from environment variable with fallback to us-west-1
        aws_region = os.environ.get('AWS_SECRETS_MANAGER_REGION', 'us-west-1')
        
        # Initialize AWS Secrets Manager client
        secrets_client = boto3.client('secretsmanager', region_name=aws_region)
        
        # Get secret ID from environment variable
        secret_id = os.environ.get('WEBHOOK_SECRET_ID')
        if not secret_id:
            print("WEBHOOK_SECRET_ID environment variable not set, webhook authentication will not be used")
            return None
        
        # Get secret from AWS Secrets Manager
        response = secrets_client.get_secret_value(SecretId=secret_id)
        # Return the secret as plain text, not JSON
        return response['SecretString']
        
    except Exception as e:
        print(f"Error retrieving webhook secret: {e}")
        return None


def upload_to_youtube(youtube, filepath, title, description="Video uploaded by TennisBuddies", privacy_status="unlisted"):
    """
    Upload a video file to YouTube
    """
    try:
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': ['tennis', 'tennisbuddies'],
                'categoryId': '17'  # Sports category
            },
            'status': {
                'privacyStatus': privacy_status
            }
        }
            
        media = MediaFileUpload(filepath, resumable=True)
        
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )

        print("Uploading file to YouTube...")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploading... {int(status.progress() * 100)}%")

        video_id = response.get('id')
        print(f"Upload Complete! Video ID: {video_id}")
        return video_id

    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred: {e.content}")
        return None
    except Exception as e:
        print(f"An error occurred during upload: {e}")
        return None


def lambda_handler(event, context):
    """Lambda function that downloads an S3 object and uploads it to YouTube
    
    Parameters
    ----------
    event: dict, required
        Input event data with s3_key and optional YouTube metadata
    
    context: object, required
        Lambda Context runtime methods and attributes
    
    Returns
    ------
    dict: Object information including YouTube video ID
    """
    
    # Get the S3 key from the event
    s3_key = event.get('s3_key')
    
    # Get YouTube metadata from the event or use defaults
    video_title = event.get('title', f"TennisBuddies - {os.path.basename(s3_key)}")
    video_description = event.get('description', "Video uploaded by TennisBuddies")
    privacy_status = event.get('privacy_status', 'unlisted')
    
    # Get webhook URL if provided
    webhook_url = event.get('webhook_url')
    
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
        
        # Log the information
        print(f"Downloaded {s3_key} from {bucket_name}")
        # print(f"File Type: {file_type}")
        print(f"File Size: {file_size} bytes")
        
        # Get authenticated YouTube service
        youtube = get_authenticated_service()
        
        # Upload video to YouTube
        video_id = upload_to_youtube(
            youtube,
            local_file_path,
            title=video_title,
            description=video_description,
            privacy_status=privacy_status
        )
        
        if not video_id:
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Failed to upload video to YouTube"
                }),
            }
            
        # Send webhook notification if webhook_url is provided
        webhook_response = None
        if webhook_url and video_id:
            try:
                # Get webhook secrets if available
                webhook_secret = get_webhook_secret()
                
                webhook_payload = {
                    "youtube_video_id": video_id
                }
                
                # Convert payload to JSON string for signature calculation
                payload_json = json.dumps(webhook_payload)
                
                # Set up headers
                headers = {
                    'Content-Type': 'application/json'
                }
                
                # Add signature if webhook secret is available
                if webhook_secret:
                    # Create HMAC SHA256 signature
                    import hmac
                    import hashlib
                    
                    signature = hmac.new(
                        webhook_secret.encode('utf-8'),
                        payload_json.encode('utf-8'),
                        hashlib.sha256
                    ).hexdigest()
                    
                    # Add signature to headers
                    headers['x-webhook-signature'] = signature
                
                # Send the webhook request with headers
                webhook_response = requests.post(
                    webhook_url, 
                    headers=headers,
                    data=payload_json
                )
                
                print(f"Webhook notification sent to {webhook_url}. Response: {webhook_response.status_code}")
            except Exception as e:
                print(f"Error sending webhook notification: {str(e)}")
        
        # Clean up
        os.remove(local_file_path)
        print(f"Removed temporary file: {local_file_path}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "s3_key": s3_key,
                "fileSize": file_size,
                "youtubeVideoId": video_id,
                "youtubeUrl": f"https://www.youtube.com/watch?v={video_id}",
                "webhookResponse": webhook_response.status_code if webhook_response else None
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
