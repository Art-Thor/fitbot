# /Users/aholubov/Desktop/fittest/fitbot/src/app/main.py
import os
import asyncio
import time
from typing import Optional

from fastapi import FastAPI # type: ignore
from slack_bolt.async_app import AsyncApp # type: ignore
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler # type: ignore
from alembic.config import Config # type: ignore
from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .config import settings
from .utils.logging import setup_logger
from .slack_app import register_handlers
from .metrics import start_metrics_server

logger = setup_logger(__name__, level=settings.log_level)

# FastAPI app
app = FastAPI()

# Bolt app
bolt_app = AsyncApp(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
    process_before_response=True,
    logger=logger
)

# Global socket handler
socket_handler: Optional[AsyncSocketModeHandler] = None

@app.get("/health")
async def health():
    return {"status": "ok"}

async def wait_for_db(max_retries: int = 5, retry_interval: int = 5):
    """Wait for database to be ready."""
    engine = create_async_engine(settings.database_url)
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

async def start_slack_app():
    """Start the Slack app in socket mode."""
    try:
        # Register all handlers
        register_handlers(bolt_app)
        
        # Start socket mode handler
        global socket_handler
        socket_handler = AsyncSocketModeHandler(bolt_app, settings.slack_app_token)
        await socket_handler.start_async()
        logger.info("Socket Mode handler started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start Slack app: {e}")
        # Don't crash, just log error

@app.on_event("startup")
async def startup_event():
    try:
        # 1) Wait for database
        await wait_for_db()
        
        # 2) Run migrations
        init_db()
        
        # 3) Start metrics server
        start_metrics_server()
        
        # 4) Start Slack app
        asyncio.create_task(start_slack_app())
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        # Don't crash, just log error

@app.on_event("shutdown")
async def shutdown_event():
    global socket_handler
    if socket_handler:
        await socket_handler.close()
        logger.info("Socket Mode handler closed")
    logger.info("Application shutdown complete")