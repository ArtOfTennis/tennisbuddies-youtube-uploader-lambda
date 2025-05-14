import json
import boto3
import os
import mimetypes
import requests
import ffmpeg
import uuid
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


def get_video_duration(video_path):
    """
    Get the duration of a video file in milliseconds
    
    Returns:
        int: Duration of the video in milliseconds
    """
    try:
        probe = ffmpeg.probe(video_path)
        video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        
        if video_info is None:
            print("No video stream found")
            return None
        
        # Get duration in seconds (as a float)
        if 'duration' in video_info:
            duration_sec = float(video_info['duration'])
        elif 'duration' in probe['format']:
            duration_sec = float(probe['format']['duration'])
        else:
            print("Duration not found in video or format information")
            return None
        
        # Convert to milliseconds
        duration_ms = int(duration_sec * 1000)
        print(f"Video duration: {duration_ms} ms")
        return duration_ms
    except Exception as e:
        print(f"Error getting video duration: {e}")
        return None


def generate_thumbnail(video_path, duration_ms=None):
    """
    Generate a thumbnail from the middle of a video file
    with the same dimensions as the original video
    
    Parameters:
        video_path (str): Path to the video file
        duration_ms (int, optional): Duration of the video in milliseconds. If None, it will be calculated.
    
    Returns:
        str: Path to the generated thumbnail file, or None if generation failed
    """
    try:
        # Create a unique filename for the thumbnail
        thumbnail_filename = f"{uuid.uuid4()}.jpg"
        thumbnail_path = f'/tmp/{thumbnail_filename}'
        
        # Print details of the file we're trying to process
        print(f"Attempting to generate thumbnail from: {video_path}")
        print(f"Target thumbnail path: {thumbnail_path}")
        
        # Check if video file exists and is accessible
        if not os.path.exists(video_path):
            print(f"Error: Video file does not exist: {video_path}")
            return None
            
        if not os.access(video_path, os.R_OK):
            print(f"Error: Video file is not readable: {video_path}")
            return None
        
        # Get video information to determine dimensions and duration if not provided
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            
            if video_stream is None:
                print("No video stream found")
                return None
            
            print(f"Original video dimensions: {video_stream.get('width')}x{video_stream.get('height')}")
            
            # Calculate duration if not provided
            if duration_ms is None:
                if 'duration' in video_stream:
                    duration_sec = float(video_stream['duration'])
                elif 'duration' in probe['format']:
                    duration_sec = float(probe['format']['duration'])
                else:
                    print("Duration not found in video or format information")
                    return None
                
                duration_ms = int(duration_sec * 1000)
                print(f"Calculated video duration: {duration_ms} ms")
        except Exception as e:
            print(f"Error probing video file: {e}")
            return None
        
        # Calculate the middle point of the video in seconds
        middle_point_sec = duration_ms / 2000  # Convert ms to seconds and find middle
        print(f"Using middle point for thumbnail: {middle_point_sec} seconds")
        
        # Verify the /tmp directory is writable
        print(f"Checking if /tmp directory is writable: {os.access('/tmp', os.W_OK)}")
        
        # Try using ffmpeg-python library first
        ffmpeg_success = False
        try:
            print("Attempting to generate thumbnail using ffmpeg-python...")
            print(f"Creating thumbnail at path: {thumbnail_path} using middle point {middle_point_sec}")
            
            # Ensure thumbnail directory exists
            # os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
            
            # Run the ffmpeg command with full paths
            process = (
                ffmpeg
                .input(video_path, ss=middle_point_sec)
                .output(thumbnail_path, vframes=1)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            # Always print ffmpeg output
            print(f"ffmpeg stdout: {process[0].decode('utf-8')}")
            print(f"ffmpeg stderr: {process[1].decode('utf-8')}")
            print("ffmpeg command executed successfully using ffmpeg-python")
            
            # Print the actual ffmpeg command that was run
            print(f"ffmpeg command that was executed: {' '.join(ffmpeg.input(video_path, ss=middle_point_sec).output(thumbnail_path, vframes=1).compile())}")
            
            ffmpeg_success = True
        except ffmpeg.Error as e:
            print(f"ffmpeg stderr: {e.stderr.decode('utf-8') if hasattr(e, 'stderr') else 'No stderr'}")
            print(f"ffmpeg stdout: {e.stdout.decode('utf-8') if hasattr(e, 'stdout') else 'No stdout'}")
            
        
        # List the files in /tmp to debug
        print(f"Files in /tmp: {os.listdir('/tmp')}")
        
        # Check if the thumbnail file was created in a subdirectory
        if not os.path.exists(thumbnail_path):
            print(f"Thumbnail not found at {thumbnail_path}, checking subdirectories...")
            # Try to find the thumbnail in subdirectories
            for root, dirs, files in os.walk('/tmp'):
                for file in files:
                    if thumbnail_filename in file:
                        print(f"Found thumbnail at: {os.path.join(root, file)}")
                        thumbnail_path = os.path.join(root, file)
                        break
        
        # Verify the thumbnail was actually created
        if os.path.exists(thumbnail_path):
            size = os.path.getsize(thumbnail_path)
            print(f"Thumbnail file exists with size: {size} bytes")
            if size > 0:
                print(f"Thumbnail generated at {thumbnail_path}")
                return thumbnail_path
            else:
                print(f"Thumbnail file is empty (0 bytes)")
                return None
        else:
            print(f"Thumbnail generation failed: file not found at {thumbnail_path}")
            return None
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        # Show the traceback for better debugging
        import traceback
        print(traceback.format_exc())
        return None


def upload_to_s3(local_file_path, bucket_name, key):
    """
    Upload a file to S3 bucket
    
    Returns:
        str: The S3 URL of the uploaded file, or None if upload fails
    """
    try:
        # Verify the file exists before trying to upload
        if not os.path.exists(local_file_path):
            print(f"File does not exist: {local_file_path}")
            return None
            
        s3 = boto3.client('s3')
        s3.upload_file(local_file_path, bucket_name, key)
        
        # Generate the S3 URL
        region = os.environ.get('AWS_SECRETS_MANAGER_REGION', 'us-west-1')
        s3_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{key}"
        
        print(f"File uploaded to S3: {s3_url}")
        return s3_url
    except Exception as e:
        print(f"Error uploading to S3: {e}")
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
    # Get the thumbnail bucket name from environment variable
    thumbnail_bucket_name = os.environ.get('S3_THUMBNAIL_BUCKET_NAME')
    
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
        print(f"File Size: {file_size} bytes")
        
        # Get video duration in milliseconds
        duration_ms = get_video_duration(local_file_path)
        
        # Generate thumbnail from video
        thumbnail_path = generate_thumbnail(local_file_path, duration_ms)
        
        # Define thumbnail S3 key and upload to S3
        thumbnail_s3_key = f"{os.path.basename(s3_key)}-thumbnail.jpg"
        thumbnail_url = None
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            # Upload to the dedicated thumbnail bucket
            thumbnail_url = upload_to_s3(thumbnail_path, thumbnail_bucket_name, thumbnail_s3_key)
        else:
            print(f"Thumbnail file does not exist or was not generated correctly")
            thumbnail_path = None  # Reset to None if file doesn't exist
        
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
                    "youtube_video_id": video_id,
                    "thumbnail_url": thumbnail_url,
                    "duration": duration_ms
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
        try:
            os.remove(local_file_path)
            print(f"Removed temporary file: {local_file_path}")
        except Exception as e:
            print(f"Error removing temporary file: {str(e)}")
        
        # Only try to remove the thumbnail file if it exists
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                os.remove(thumbnail_path)
                print(f"Removed temporary thumbnail file: {thumbnail_path}")
            except Exception as e:
                print(f"Error removing temporary thumbnail file: {str(e)}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "s3_key": s3_key,
                "fileSize": file_size,
                "youtubeVideoId": video_id,
                "youtubeUrl": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnailUrl": thumbnail_url,
                "duration": duration_ms,
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
