# src/app/models/challenge.py

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Enum, Boolean, Integer
from sqlalchemy.orm import relationship
import enum

from .base import Base, TimestampedModel

class ActivityType(enum.Enum):
    WALKING = "walking"
    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    CALORIES = "calories"

class Challenge(Base, TimestampedModel):
    __tablename__ = "challenges"

    slack_channel_id = Column(String, nullable=False, unique=True)
    activity_type     = Column(Enum(ActivityType), nullable=False)
    start_date        = Column(DateTime, nullable=False)
    end_date          = Column(DateTime, nullable=False)
    is_active         = Column(Boolean, default=True)
    results           = relationship("Result", back_populates="challenge")


class Result(Base, TimestampedModel):
    __tablename__ = "results"

    user_id          = Column(String, nullable=False, index=True)
    date             = Column(DateTime, nullable=False)
    value            = Column(Float, nullable=False)
    unit             = Column(String, nullable=False)
    screenshot_url   = Column(String, nullable=True)
    is_validated     = Column(Boolean, default=False)
    validation_error = Column(String, nullable=True)
    validated_by     = Column(String, nullable=True)
    validated_at     = Column(DateTime, nullable=True)

    challenge_id     = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    challenge        = relationship("Challenge", back_populates="results")