FROM python:3.10-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install

# Copy app code
COPY src/QA_pipeline.py .
COPY src/logger.py .
COPY src/main.py .
COPY src/telegram_handler.py .
COPY src/mycrawler.py .
COPY src/indexer.py .

# Expose port (Cloud Run expects 8080)
EXPOSE 8080

# Run FastAPI. Use the PORT environment variable provided by Cloud Run
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
