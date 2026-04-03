"""Streaming logger for real-time log output from nodes."""

import logging
from typing import Callable, Optional


class StreamingLogger(logging.Logger):
    """Logger that streams log records to a callback function.

    Usage:
        def on_log(message: str) -> None:
            print(f"Received: {message}")

        logger = StreamingLogger("node_logger", on_log)
        logger.info("Starting execution")
    """

    def __init__(
        self,
        name: str,
        on_log: Callable[[str], None],
        level: int = logging.INFO,
    ):
        """Initialize streaming logger.

        Args:
            name: Logger name
            on_log: Callback function called for each log message
            level: Logging level
        """
        super().__init__(name, level)
        self.on_log = on_log

        # Create handler that sends to callback
        handler = logging.StreamHandler(_CallbackStream(on_log))
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        self.addHandler(handler)
        self.propagate = False


class _CallbackStream:
    """Fake file-like object that redirects writes to callback."""

    def __init__(self, on_log: Callable[[str], None]):
        self.on_log = on_log

    def write(self, message: str) -> None:
        """Write message to callback."""
        if message.strip():  # Skip empty messages
            self.on_log(message.rstrip())

    def flush(self) -> None:
        """Flush is a no-op for callback stream."""
        pass


def create_streaming_logger(
    name: str,
    on_log: Callable[[str], None],
    level: int = logging.INFO,
) -> StreamingLogger:
    """Create a streaming logger instance.

    Args:
        name: Logger name
        on_log: Callback function for log messages
        level: Logging level

    Returns:
        Configured StreamingLogger instance
    """
    return StreamingLogger(name, on_log, level)
