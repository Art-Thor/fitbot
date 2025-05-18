FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ /app/src/

# Set environment variables
ENV PYTHONPATH=/app

# Run Celery worker
CMD ["celery", "-A", "src.app.tasks:celery_app", "worker", "--loglevel=info", "-Q", "submissions"] 