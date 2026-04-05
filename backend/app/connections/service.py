"""Connection testing service using typed connection classes."""

import logging

from app.schemas.connection import assemble_connection

logger = logging.getLogger(__name__)


class ConnectionTestResult:
    """Result of a connection test."""

    def __init__(self, success: bool, message: str, error: str | None = None):
        self.success = success
        self.message = message
        self.error = error

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        result: dict = {"success": self.success, "message": self.message}
        if self.error:
            result["error"] = self.error
        return result


async def test_connection(
    connection_type: str, config: dict, secrets: dict
) -> ConnectionTestResult:
    """Test a connection by assembling the typed class and calling its test() method.

    Args:
        connection_type: Type identifier (postgres, clickhouse, s3, spark)
        config: Configuration dict
        secrets: Secrets dict

    Returns:
        ConnectionTestResult with outcome
    """
    try:
        conn = assemble_connection(connection_type, config, secrets)
        success, message, error = await conn.test()
        return ConnectionTestResult(success=success, message=message, error=error)

    except ValueError as e:
        return ConnectionTestResult(
            success=False,
            message=f"Unknown connection type: {connection_type}",
            error=str(e),
        )

    except Exception as e:
        logger.exception("Unexpected error during connection test")
        return ConnectionTestResult(
            success=False,
            message="Failed to test connection",
            error=str(e),
        )
