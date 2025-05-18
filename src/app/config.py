import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/fitbot")
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    # Slack
    slack_bot_token: str = os.getenv("SLACK_BOT_TOKEN")
    slack_app_token: str = os.getenv("SLACK_APP_TOKEN")
    slack_signing_secret: str = os.getenv("SLACK_SIGNING_SECRET")
    workflow_bot_id: str = os.getenv("WORKFLOW_BOT_ID")
    
    # Ollama
    ollama_url: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    
    # OCR
    ocr_validation_tolerance: float = 0.1  # 10% tolerance for OCR validation
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings() 