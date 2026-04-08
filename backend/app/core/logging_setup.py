"""Application logging setup with separate handlers for server and runner."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _make_formatter(fmt: str = DEFAULT_LOG_FORMAT) -> logging.Formatter:
    return logging.Formatter(fmt, datefmt=DEFAULT_DATE_FORMAT)


def setup_server_logging(
    log_dir: str | Path,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 3,
) -> None:
    """Configure root logger for FastAPI service.

    Logs go to:
      - STDOUT (INFO+)
      - {log_dir}/server.log (DEBUG+, rotating)

    Args:
        log_dir: Directory for log files
        level: Minimum logging level
        max_bytes: Max size per log file before rotation
        backup_count: Number of rotated files to keep
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Clear existing handlers
    root.handlers.clear()

    # STDOUT handler — INFO+
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(_make_formatter())
    root.addHandler(console)

    # File handler — server.log, rotating
    server_file = RotatingFileHandler(
        log_path / "server.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    server_file.setLevel(logging.DEBUG)
    server_file.setFormatter(_make_formatter())
    root.addHandler(server_file)


def setup_runner_logging(
    log_dir: str | Path,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
) -> None:
    """Configure logger for PipelineRunner (main process).

    Logs go to:
      - STDOUT (INFO+)
      - {log_dir}/runner.log (DEBUG+, rotating)

    This is separate from the root logger so FastAPI logs
    and runner logs don't duplicate each other.

    Args:
        log_dir: Directory for log files
        level: Minimum logging level
        max_bytes: Max size per log file before rotation
        backup_count: Number of rotated files to keep
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    runner_logger = logging.getLogger("app.orchestration.runner")
    runner_logger.setLevel(logging.DEBUG)
    runner_logger.propagate = False  # Don't send to root/FastAPI handlers
    runner_logger.handlers.clear()

    # STDOUT handler — INFO+
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(_make_formatter())
    runner_logger.addHandler(console)

    # File handler — runner.log, rotating
    runner_file = RotatingFileHandler(
        log_path / "runner.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    runner_file.setLevel(logging.DEBUG)
    runner_file.setFormatter(_make_formatter())
    runner_logger.addHandler(runner_file)
