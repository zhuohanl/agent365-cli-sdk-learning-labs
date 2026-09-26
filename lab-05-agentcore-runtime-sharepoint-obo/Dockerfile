FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    --index-url https://packagefeedproxy.microsoft.io/pypi/simple/ \
    "boto3>=1.39.8,<2" \
    "PyJWT[crypto]==2.10.1"

COPY src ./src

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["python", "-m", "src.runtime_app"]
