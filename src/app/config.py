import os
from pydantic_settings import BaseSettings
from typing import Optional, List
from pydantic import field_validator

class Settings(BaseSettings):
    # Database
    database_url: str = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/fitbot")
    
    # Redis
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    
    # Slack
    slack_bot_token: str = os.environ["SLACK_BOT_TOKEN"]
    slack_app_token: str = os.environ["SLACK_APP_TOKEN"]
    slack_signing_secret: str = os.environ["SLACK_SIGNING_SECRET"]
    workflow_bot_id: str = os.environ["WORKFLOW_BOT_ID"]
    
    # Ollama
    ollama_url: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    
    # OCR
    ocr_validation_tolerance: float = 0.1  # 10% tolerance for OCR validation
    
    # Logging
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")
    
    # Challenge channels
    challenge_channels: List[str] = []
    
    @field_validator("challenge_channels", mode="before")
    @classmethod
    def parse_challenge_channels(cls, v):
        if isinstance(v, str):
            if not v:
                return []
            return [c.strip() for c in v.split(",") if c.strip()]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings() 