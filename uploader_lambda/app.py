import json

# import requests


def lambda_handler(event, context):
    """Simple Lambda function that prints and returns Hello World!
    
    Parameters
    ----------
    event: dict, required
        Input event data
    
    context: object, required
        Lambda Context runtime methods and attributes
    
    Returns
    ------
    dict: A simple hello world message
    """
    
    print("Hello World!")
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Hello World!"
        }),
    }
