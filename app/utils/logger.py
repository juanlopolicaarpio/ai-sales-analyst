import os
import sys
import logging
from datetime import datetime
from loguru import logger
from pathlib import Path

from app.config import settings

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Configure loguru logger
config = {
    "handlers": [
        {
            "sink": sys.stderr,
            "format": "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            "level": settings.LOG_LEVEL,
        },
        {
            "sink": logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log",
            "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            "level": settings.LOG_LEVEL,
            "rotation": "00:00",  # Create a new file at midnight
            "retention": "14 days",  # Keep logs for 14 days
            "compression": "zip",  # Compress rotated logs
        },
    ],
}

# Apply configuration
logger.configure(**config)


class InterceptHandler(logging.Handler):
    """
    Intercept standard logging messages toward Loguru
    
    This interceptor enables redirecting stdlib logging to loguru,
    making all log records go through loguru by default
    """

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where this was logged
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# Intercept all standard library logging
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

# Set logging levels for third-party libraries to avoid excessive logs
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)