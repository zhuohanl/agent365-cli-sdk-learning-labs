FROM openpolicyagent/opa:1.10.1-static AS opa

FROM python:3.12-slim

WORKDIR /app

COPY --from=opa /opa /usr/local/bin/opa

RUN pip install --no-cache-dir \
    --index-url https://packagefeedproxy.microsoft.io/pypi/simple/ \
    "PyJWT[crypto]==2.10.1" \
    "python-docx==1.2.0"

COPY src ./src
COPY gate2 ./gate2

RUN opa check --strict /app/gate2/policies \
    && opa test /app/gate2/policies

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["python", "-m", "gate2.mcp_app"]
