# YouTube Uploader Lambda Function

A simple AWS Lambda function that prints "Hello World!" when invoked directly.

## Prerequisites

- AWS SAM CLI installed
- Docker installed
- AWS CLI configured with appropriate credentials

## Building the Application

To build the application, run:

```bash
sam build
```

## Local Testing

To test the Lambda function locally, run:

```bash
sam local invoke YouTubeUploaderFunction
```

## Deploying to AWS

To deploy the application to AWS, run:

```bash
sam deploy --guided
```

Follow the prompts to complete the deployment.

## Invoking the Lambda Function

After deployment, you can invoke the Lambda function directly using the AWS CLI:

```bash
aws lambda invoke --function-name youtube-uploader-YouTubeUploaderFunction-XXXXXXXXXXXX outfile.txt
```

Replace `XXXXXXXXXXXX` with the unique identifier that AWS assigns to your function after deployment.

To see the output, check the `outfile.txt` file or CloudWatch logs.
