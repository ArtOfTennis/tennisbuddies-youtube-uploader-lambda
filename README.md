# YouTube Uploader Lambda Function

AWS Lambda function that uploads video files from an S3 bucket to YouTube using the YouTube API.

## Overview

This Lambda function:
1. Retrieves a video file from an S3 bucket
2. Authenticates with the YouTube API using credentials stored in AWS Secrets Manager
3. Uploads the video to YouTube with specified metadata
4. Returns the YouTube video ID and URL

## Prerequisites

- AWS SAM CLI installed
- Docker installed
- AWS CLI configured with appropriate credentials
- YouTube API credentials stored in AWS Secrets Manager

## Environment Variables

The function uses the following environment variables:
- `S3_BUCKET_NAME`: The S3 bucket containing video files (either `tennisbuddies-club` for dev or `tennisbuddies-club-prod` for prod)
- `YOUTUBE_API_SECRET_ID`: The ID of the Secret in AWS Secrets Manager containing YouTube API credentials (set to `TennisBuddies/YoutubeAPI`)
- `AWS_SECRETS_MANAGER_REGION`: The AWS region for Secrets Manager (set to `us-west-1`)

## YouTube API Credentials

The function expects YouTube API credentials to be stored in AWS Secrets Manager with the following structure:
```json
{
  "TOKEN": "your_token",
  "REFRESH_TOKEN": "your_refresh_token",
  "TOKEN_URI": "https://oauth2.googleapis.com/token",
  "CLIENT_ID": "your_client_id",
  "CLIENT_SECRET": "your_client_secret"
}
```

## Building the Application

To build the application, run:

```bash
sam build
```

## Deploying to AWS

To deploy to the dev environment:

```bash
sam deploy
```

To deploy to production:

```bash
sam deploy --config-env prod
```

## Stack Configuration

The application uses the following configuration:
- Stack name: `youtube-uploader`
- Region: `us-west-1`
- ECR Repository: `008082804869.dkr.ecr.us-west-1.amazonaws.com/youtubeuploaderee8a41e3/youtubeuploaderfunctiond54705c8repo`
- Timeout: 900 seconds (15 minutes)
- Memory: 1024 MB

## IAM Permissions

The Lambda function has the following permissions:
- Read access to the S3 bucket (`tennisbuddies-club` for dev or `tennisbuddies-club-prod` for prod)
- Access to retrieve secret values from AWS Secrets Manager for the secret `TennisBuddies/YoutubeAPI`

## Invoking the Lambda Function

You can invoke the Lambda function with an event payload like this:

```json
{
  "s3_key": "path/to/your/video.mp4",
  "title": "Your Video Title",
  "description": "Your video description",
  "privacy_status": "unlisted"
}
```

Example using AWS CLI:

```bash
aws lambda invoke --function-name youtube-uploader-YouTubeUploaderFunction-XXXXXXXXXXXX \
  --payload '{"s3_key":"videos/match.mp4","title":"Tennis Match Highlights","description":"Exciting tennis match","privacy_status":"unlisted"}' \
  response.json
```

The response will include the YouTube video ID and URL if successful.
