FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY web ./web
COPY config.yaml .

EXPOSE 8000
# Reads secrets from the environment (docker-compose passes the .env file).
CMD ["python", "-m", "bot.main"]
