# /Users/aholubov/Desktop/fittest/fitbot/src/app/main.py
import os
import asyncio
import uvicorn
import multiprocessing
from typing import Optional
import logging

from fastapi import FastAPI # type: ignore
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler # type: ignore
from alembic.config import Config # type: ignore
from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .config import settings
from .utils.logging import setup_logger
from .slack_app import bolt_app
from .metrics import start_metrics_server
from .models.database import check_db_connection

logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI()

# Global socket handler
socket_handler: Optional[AsyncSocketModeHandler] = None

# Initialize Socket Mode handler
handler = AsyncSocketModeHandler(bolt_app, os.environ["SLACK_APP_TOKEN"])

def run_slack_app():
    """Run the Slack Bolt app in a separate process."""
    bolt_app.start()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

async def wait_for_db(max_retries: int = 5, retry_interval: int = 5):
    """Wait for database to be ready."""
    from .models.database import engine
    for i in range(max_retries):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                logger.info("Database is ready")
                return
        except Exception as e:
            if i == max_retries - 1:
                raise
            logger.warning(f"Database not ready, retrying in {retry_interval} seconds: {e}")
            await asyncio.sleep(retry_interval)

def init_db():
    """Run Alembic migrations from src/alembic."""
    try:
        # Get the absolute path to the project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ini_path = os.path.join(project_root, "alembic.ini")
        
        if not os.path.exists(ini_path):
            logger.error(f"Alembic config file not found at {ini_path}")
            return  # Don't crash, just log error
            
        logger.info(f"Running migrations using {ini_path}")
        
        # Configure Alembic
        cfg = Config(ini_path)
        cfg.set_main_option("script_location", os.path.join(project_root, "alembic"))
        
        try:
            # Run migrations
            command.upgrade(cfg, "head")
            logger.info("Migrations applied successfully")
        except Exception as e:
            logger.error(f"Failed to apply migrations: {e}")
            # Don't crash, just log error
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Don't crash, just log error

@app.on_event("startup")
async def on_startup():
    """Initialize services on startup."""
    try:
        # 1) Wait for database
        await wait_for_db()
        
        # 2) Initialize database
        from .models.database import async_session, Base, engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        # 3) Start metrics server
        start_metrics_server()
        
        # 4) Check database connection
        if await check_db_connection():
            logger.info("Database is ready")
        else:
            logger.error("Database connection failed")
            raise Exception("Database connection failed")
        
        # 5) Log configured challenge channels
        logger.info(f"💡 Configured challenge_channels = {settings.challenge_channels!r}")
        
        # 6) Start Slack Bolt app in a separate process
        slack_process = multiprocessing.Process(target=run_slack_app)
        slack_process.start()
        logger.info("Started Slack Bolt app in a separate process")
        
        logger.info("Application startup completed successfully")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

@app.on_event("shutdown")
async def on_shutdown():
    """Cleanup on shutdown."""
    if handler:
        await handler.close()
        logger.info("Socket Mode handler closed")
    await bolt_app.stop()
    logger.info("Application shutdown complete")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))