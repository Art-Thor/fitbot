import logging
import sys
from typing import Optional
from ..config import settings

def setup_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Set up a logger with the specified name and level."""
    logger = logging.getLogger(name)
    
    if level is None:
        level = settings.log_level
    
    logger.setLevel(getattr(logging, level.upper()))
    
    # Create console handler if it doesn't exist
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper()))
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
    
    return logger 