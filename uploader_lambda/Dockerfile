FROM public.ecr.aws/lambda/python:3.9

# Install ffmpeg and ffprobe
RUN yum update -y && \
    yum install -y wget tar xz && \
    mkdir -p /tmp/ffmpeg && \
    cd /tmp/ffmpeg && \
    wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz && \
    tar xf ffmpeg-release-amd64-static.tar.xz && \
    mv ffmpeg-*-amd64-static/ffmpeg ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ && \
    rm -rf /tmp/ffmpeg

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .

CMD ["app.lambda_handler"] 