# src/app/workflow_handler.py

from slack_bolt.async_app import AsyncApp # type: ignore
from .config import settings
from .tasks import process_submission
from .utils.logging import setup_logger
from .metrics import task_total, task_duration
import time
from celery.exceptions import TimeoutError # type: ignore

logger = setup_logger(__name__, level=settings.log_level)

def register_workflow_listener(app: AsyncApp):
    """Register the workflow message listener."""
    
    @app.message("")  # catch all messages
    async def handle_workflow_message(message, say):
        """Handle messages from the workflow bot."""
        start_time = time.time()
        task_total.labels(task_name='workflow_message', status='started').inc()
        
        try:
            # only listen in challenge channels
            if message.get("channel_type") != "channel":
                return
                
            channel = message["channel"]
            user = message.get("user")
            ts = message.get("ts")
            
            if not all([channel, user, ts]):
                logger.warning("Missing required message fields")
                return
                
            logger.info(f"New submission from {user} in {channel}")

            # Send acknowledgment
            await say(text="⏳ Processing...", thread_ts=ts)
            
            # Submit task to Celery
            task = process_submission.delay({
                "user": user,
                "text": message.get("text", ""),
                "files": message.get("files", []),
                "channel": channel,
                "ts": ts
            })
            logger.info(f"Submitted task {task.id} to Celery")
            
            try:
                # Wait for task result with timeout
                res = task.get(timeout=30)
                await say(text=res["message"], thread_ts=ts)
                
                task_total.labels(task_name='workflow_message', status='success').inc()
                task_duration.labels(task_name='workflow_message').observe(time.time() - start_time)
                
            except TimeoutError:
                logger.error(f"Task {task.id} timed out after 30 seconds")
                await say(
                    text="⚠️ Processing is taking longer than expected. We'll notify you when it's done.",
                    thread_ts=ts
                )
                task_total.labels(task_name='workflow_message', status='timeout').inc()
                
            except Exception as e:
                logger.error(f"Error processing task {task.id}: {e}")
                await say(
                    text=f"❌ Error processing submission: {str(e)}",
                    thread_ts=ts
                )
                task_total.labels(task_name='workflow_message', status='error').inc()
                
        except Exception as e:
            logger.error(f"Error handling workflow message: {e}")
            task_total.labels(task_name='workflow_message', status='error').inc()
            task_duration.labels(task_name='workflow_message').observe(time.time() - start_time)
            
            # Try to send error message if we have the thread_ts
            try:
                if 'ts' in message:
                    await say(
                        text=f"❌ Error: {str(e)}",
                        thread_ts=message['ts']
                    )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")