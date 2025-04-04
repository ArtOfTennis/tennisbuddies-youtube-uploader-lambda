import json

import pytest

from uploader_lambda import app


@pytest.fixture()
def s3_event():
    """ Generates S3 Event for direct Lambda invocation"""

    return {
        "s3BucketName": "my-youtube-videos-bucket",
        "s3ObjectKey": "videos/my-awesome-video.mp4"
    }


def test_lambda_handler(s3_event):
    ret = app.lambda_handler(s3_event, "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert "message" in ret["body"]
    assert data["message"] == "hello world"
