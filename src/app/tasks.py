# src/app/tasks.py

from celery import Celery
from .models.database import async_session
from .models.challenge import Result, Challenge
from .utils.ocr import VisionService, validate_result
from .clients.ollama import OllamaClient
from .metrics import task_total, task_duration, ocr_attempts_total, ocr_duration, ollama_requests_total, ollama_duration
from datetime import datetime
import time
import json
from sqlalchemy import select # type: ignore
from .config import settings
from .utils.logging import setup_logger

logger = setup_logger(__name__, level=settings.log_level)

# Initialize Celery
celery_app = Celery(
    'fitbot',
    broker=settings.redis_url,
    backend=settings.redis_url,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Initialize services
vision_service = VisionService()
ollama_client = OllamaClient()

@celery_app.task(name="process_submission", bind=True, max_retries=3)
def process_submission(self, event):
    """Process a fitness challenge submission."""
    start_time = time.time()
    task_total.labels(task_name='process_submission', status='started').inc()
    
    try:
        logger.info(f"Processing submission: {event}")
        
        # Extract submission details
        user_id = event.get('user')
        text = event.get('text', '')
        files = event.get('files', [])
        channel = event.get('channel')
        ts = event.get('ts')
        
        if not all([user_id, channel, ts]):
            raise ValueError("Missing required fields: user, channel, or ts")
            
        # Try to extract metrics from text first
        metrics = None
        if text:
            try:
                ollama_start = time.time()
                metrics = ollama_client.extract_metrics(text)
                ollama_duration.observe(time.time() - ollama_start)
                ollama_requests_total.labels(status='success').inc()
                logger.debug(f"Extracted metrics from text: {metrics}")
            except Exception as e:
                logger.error(f"Failed to extract metrics from text: {e}")
                ollama_requests_total.labels(status='error').inc()
        
        # If no metrics from text, try OCR on images
        if not metrics and files:
            for file in files:
                try:
                    ocr_start = time.time()
                    image_url = file.get('url_private')
                    if not image_url:
                        continue
                        
                    # Download and analyze image
                    image_bytes = vision_service.download_image(image_url, settings.slack_bot_token)
                    ocr_text = vision_service.analyze(image_bytes)
                    
                    if ocr_text:
                        # Try to extract metrics from OCR text
                        metrics = ollama_client.extract_metrics(ocr_text)
                        if metrics:
                            break
                            
                    ocr_duration.observe(time.time() - ocr_start)
                    ocr_attempts_total.labels(status='success').inc()
                    
                except Exception as e:
                    logger.error(f"Failed to process image: {e}")
                    ocr_attempts_total.labels(status='error').inc()
        
        if not metrics:
            raise ValueError("Could not extract metrics from submission")
            
        # Validate metrics
        if not all(k in metrics for k in ['date', 'value', 'unit']):
            raise ValueError("Missing required metrics: date, value, or unit")
            
        try:
            date = datetime.fromisoformat(metrics['date'])
            value = float(metrics['value'])
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid date or value format: {e}")
            
        # Store submission in database
        import asyncio
        loop = asyncio.get_event_loop()
        
        async def _save():
            async with async_session() as db:
                # Get active challenge
                stmt = select(Challenge).where(
                    Challenge.slack_channel_id == channel,
                    Challenge.is_active == True
                )
                challenge = (await db.execute(stmt)).first()
                
                if not challenge:
                    raise ValueError("No active challenge in this channel")
                    
                # Create result
                result = Result(
                    user_id=user_id,
                    date=date,
                    value=value,
                    unit=metrics['unit'],
                    screenshot_url=files[0].get('url_private') if files else None,
                    is_validated=True,
                    challenge_id=challenge.id
                )
                
                db.add(result)
                await db.commit()
                logger.info(f"Saved result for user {user_id} in challenge {challenge.id}")
                
        loop.run_until_complete(_save())
        
        task_total.labels(task_name='process_submission', status='success').inc()
        task_duration.labels(task_name='process_submission').observe(time.time() - start_time)
        
        return {
            'status': 'success',
            'message': f"✅ <@{user_id}>, your {value}{metrics['unit']} on {date.strftime('%Y-%m-%d')} has been recorded!"
        }
        
    except Exception as e:
        logger.error(f"Error processing submission: {e}")
        task_total.labels(task_name='process_submission', status='error').inc()
        task_duration.labels(task_name='process_submission').observe(time.time() - start_time)
        
        # Retry on certain errors
        if isinstance(e, (ValueError, TypeError)):
            try:
                self.retry(exc=e, countdown=5)
            except self.MaxRetriesExceededError:
                pass
                
        return {
            'status': 'error',
            'message': f"❌ Failed to process submission: {str(e)}"
        }