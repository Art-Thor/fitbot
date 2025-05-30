from prometheus_client import Counter, Histogram, start_http_server
import os
from .config import settings
from .utils.logging import setup_logger

logger = setup_logger(__name__, level=settings.log_level)

METRICS_PORT = int(os.environ.get("METRICS_PORT", 9000))

# Task metrics
task_total = Counter(
    'celery_task_total',
    'Total number of tasks processed',
    ['task_name', 'status']
)

task_duration = Histogram(
    'celery_task_duration_seconds',
    'Task processing duration in seconds',
    ['task_name']
)

# HTTP metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# OCR metrics
ocr_attempts_total = Counter(
    'ocr_attempts_total',
    'Total number of OCR attempts',
    ['status']
)

ocr_duration = Histogram(
    'ocr_duration_seconds',
    'OCR processing duration in seconds'
)

# Ollama metrics
ollama_requests_total = Counter(
    'ollama_requests_total',
    'Total number of Ollama API requests',
    ['status']
)

ollama_duration = Histogram(
    'ollama_duration_seconds',
    'Ollama API request duration in seconds'
)

def start_metrics_server():
    """Start Prometheus metrics server on a separate port."""
    try:
        start_http_server(METRICS_PORT)
        logger.info(f"Started Prometheus metrics server on port {METRICS_PORT}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
        # Don't crash, just log error 