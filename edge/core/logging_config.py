"""
T062: Centralized Logging Configuration
Provides structured logging with multiple handlers and formatters
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs logs in JSON format for easy parsing by log aggregation systems.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, 'extra'):
            log_data['extra'] = record.extra

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """
    Colored console formatter for better readability.
    """

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        """Format with colors"""
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = "logs/edge.log",
    json_format: bool = False,
    console_output: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Configure application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (None to disable file logging)
        json_format: Use JSON format for file logs
        console_output: Enable console output
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup files to keep
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create logs directory if needed
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    root_logger.handlers = []

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)

        # Use colored formatter for console
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(numeric_level)

        # Choose formatter based on json_format flag
        if json_format:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Set specific log levels for noisy libraries
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncua').setLevel(logging.INFO)

    logging.info(f"Logging configured: level={log_level}, file={log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Example usage
if __name__ == "__main__":
    # Setup logging
    setup_logging(
        log_level="DEBUG",
        log_file="logs/test.log",
        json_format=False,
        console_output=True
    )

    # Get logger and test
    logger = get_logger(__name__)

    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    try:
        1 / 0
    except Exception as e:
        logger.exception("This is an exception with traceback")

    print("\nCheck logs/test.log for file output")
