from slack_bolt.async_app import AsyncApp
import os
from .config import settings
from .utils.logging import setup_logger
from .workflow_handler import register_workflow_listener
from .commands import register_commands, CHANNEL_ACTIVITY
from .models.database import async_session
from .models.challenge import Result
from datetime import datetime
from sqlalchemy import select, update

logger = setup_logger(__name__, level=settings.log_level)

# Initialize the Slack app with error handling
try:
    bolt_app = AsyncApp(
        token=os.environ["SLACK_BOT_TOKEN"],
        signing_secret=os.environ["SLACK_SIGNING_SECRET"],
        process_before_response=True,
        logger=logger,  # Add logger to app
        raise_error_for_unhandled_request=True  # Raise errors for unhandled requests
    )
    logger.info("Slack app initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Slack app: {e}")
    raise

@bolt_app.error
async def custom_error_handler(error, body, logger):
    """Handle errors in Slack app."""
    logger.error(f"Error: {error}")
    logger.error(f"Request body: {body}")
    return {"text": "❌ An error occurred while processing your request. Please try again."}

@bolt_app.event("message")
async def handle_message_events(body, say, logger):
    """Handle message events from the workflow bot."""
    try:
        # Check if the message is from our workflow bot
        if body.get("bot_id") != os.environ["WORKFLOW_BOT_ID"]:
            return
            
        # Get message details
        channel = body.get("channel")
        user = body.get("user")
        text = body.get("text", "")
        files = body.get("files", [])
        ts = body.get("ts")
        
        logger.info(f"Processing workflow message from {user} in {channel}")
        
        # Check if this is a challenge channel
        if not any(channel.endswith(f"-{k}") for k in CHANNEL_ACTIVITY.keys()):
            logger.debug(f"Channel {channel} is not a challenge channel")
            return
            
        # Send acknowledgment
        await say(
            text="⏳ Processing your submission...",
            thread_ts=ts
        )
        
        # Submit to Celery
        from .tasks import process_submission
        task = process_submission.delay({
            "user": user,
            "text": text,
            "files": files,
            "channel": channel,
            "ts": ts
        })
        
        logger.info(f"Submitted task {task.id} to process submission")
        
        # Wait for result
        try:
            result = task.get(timeout=30)
            await say(
                text=result["message"],
                thread_ts=ts
            )
        except Exception as e:
            logger.error(f"Error processing submission: {e}")
            await say(
                text=f"❌ Error processing submission: {str(e)}",
                thread_ts=ts
            )
            
    except Exception as e:
        logger.error(f"Error handling message event: {e}")

@bolt_app.event("reaction_added")
async def handle_reaction(body, say, logger):
    """Handle reactions for admin operations."""
    try:
        # Only process specific reactions
        if body["reaction"] not in ["🗑️", "❌"]:
            return
            
        # Get the message that was reacted to
        channel = body["item"]["channel"]
        ts = body["item"]["ts"]
        
        # Find the result in database
        async with async_session() as db:
            # First, get the message text to find the user
            from slack_sdk.web.async_client import AsyncWebClient
            client = AsyncWebClient(token=os.environ["SLACK_BOT_TOKEN"])
            response = await client.conversations_history(
                channel=channel,
                latest=ts,
                limit=1,
                inclusive=True
            )
            
            if not response["messages"]:
                return
                
            message = response["messages"][0]
            if not message.get("text", "").startswith("✅"):
                return
                
            # Extract user ID from the message
            import re
            user_match = re.search(r"<@([A-Z0-9]+)>", message["text"])
            if not user_match:
                return
                
            user_id = user_match.group(1)
            
            # Find and invalidate the result
            stmt = (
                select(Result)
                .where(
                    Result.user_id == user_id,
                    Result.is_validated == True
                )
                .order_by(Result.created_at.desc())
                .limit(1)
            )
            result = (await db.execute(stmt)).first()
            
            if result:
                await db.execute(
                    update(Result)
                    .where(Result.id == result.id)
                    .values(
                        is_validated=False,
                        validated_by=body["user"],
                        validated_at=datetime.utcnow(),
                        validation_error="Invalidated by admin"
                    )
                )
                await db.commit()
                
                # Notify in thread
                await say(
                    text=f"❌ Result invalidated by <@{body['user']}>",
                    thread_ts=ts
                )
                
    except Exception as e:
        logger.error(f"Error handling reaction: {e}")

# Register all handlers
register_workflow_listener(bolt_app)
register_commands(bolt_app)
logger.info("All handlers registered successfully") 