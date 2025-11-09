"""Logging configuration for CDD Agent.

This module sets up comprehensive logging to help debug issues:
- Logs to /tmp/cdd-agent/cdd-agent.log
- Rotating file handler (10MB max, 3 backup files)
- Debug level (verbose - captures everything)
- Includes timestamps, module names, and stack traces
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Log file configuration
LOG_DIR = Path("/tmp/cdd-agent")
LOG_FILE = LOG_DIR / "cdd-agent.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 3  # Keep last 3 rotated files


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """Set up logging with rotating file handler.

    Args:
        level: Logging level (default: DEBUG for verbose logging)

    Returns:
        Configured logger instance
    """
    # Create log directory if it doesn't exist
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Get root logger for cdd_agent
    logger = logging.getLogger("cdd_agent")
    logger.setLevel(level)

    # Remove any existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create rotating file handler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)

    # Create formatter with detailed information
    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(file_handler)

    # Also log to console for errors (optional, can be disabled)
    # Disabled by default to keep CLI output clean
    # Uncomment if you want errors to appear in terminal too:
    # console_handler = logging.StreamHandler(sys.stderr)
    # console_handler.setLevel(logging.ERROR)
    # console_handler.setFormatter(formatter)
    # logger.addHandler(console_handler)

    logger.debug("Logging initialized")
    logger.debug(f"Log file: {LOG_FILE}")
    logger.debug(f"Max size: {MAX_LOG_SIZE / 1024 / 1024}MB")
    logger.debug(f"Backup count: {BACKUP_COUNT}")

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (uses module name if not provided)

    Returns:
        Logger instance (child of cdd_agent root logger)
    """
    if name:
        return logging.getLogger(f"cdd_agent.{name}")
    else:
        return logging.getLogger("cdd_agent")


def log_exception(logger: logging.Logger, message: str, exc_info: bool = True):
    """Log an exception with full stack trace.

    Args:
        logger: Logger instance
        message: Error message
        exc_info: Whether to include exception info (default: True)
    """
    logger.error(message, exc_info=exc_info)


def get_log_file_path() -> Path:
    """Get the path to the current log file.

    Returns:
        Path to log file
    """
    return LOG_FILE


def get_log_files() -> list[Path]:
    """Get all log files (current + rotated backups).

    Returns:
        List of log file paths, sorted by modification time (newest first)
    """
    if not LOG_DIR.exists():
        return []

    # Find all log files (cdd-agent.log, cdd-agent.log.1, etc.)
    log_files = list(LOG_DIR.glob("cdd-agent.log*"))

    # Sort by modification time, newest first
    log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    return log_files


def read_recent_logs(lines: int = 50) -> str:
    """Read the most recent N lines from the log file.

    Args:
        lines: Number of lines to read from end of file

    Returns:
        Last N lines of the log file
    """
    if not LOG_FILE.exists():
        return "No log file found. Logs will be created when the agent runs."

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return "".join(recent)
    except Exception as e:
        return f"Error reading log file: {e}"


def clear_logs() -> tuple[bool, str]:
    """Clear all log files.

    Returns:
        Tuple of (success, message)
    """
    try:
        log_files = get_log_files()

        if not log_files:
            return True, "No log files to clear."

        for log_file in log_files:
            log_file.unlink()

        return True, f"Cleared {len(log_files)} log file(s)."
    except Exception as e:
        return False, f"Error clearing logs: {e}"


def get_log_stats() -> dict:
    """Get statistics about log files.

    Returns:
        Dictionary with log file stats
    """
    log_files = get_log_files()

    if not log_files:
        return {
            "total_files": 0,
            "total_size_mb": 0,
            "current_log": None,
            "oldest_log": None,
        }

    total_size = sum(f.stat().st_size for f in log_files)

    return {
        "total_files": len(log_files),
        "total_size_mb": total_size / 1024 / 1024,
        "current_log": str(log_files[0]) if log_files else None,
        "oldest_log": str(log_files[-1]) if log_files else None,
    }


# Initialize logging when module is imported
# This ensures logging is set up before any other code runs
_root_logger = setup_logging()
