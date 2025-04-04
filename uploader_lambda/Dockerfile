FROM public.ecr.aws/lambda/python:3.9

COPY . ${LAMBDA_TASK_ROOT}

# Install requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Command can be overwritten by providing a different command in the template directly.
CMD ["app.lambda_handler"] 