"""Connection testing service for validating connections."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.models.connection import ConnectionType
from app.schemas.connection import (
    ClickHouseConfig,
    ClickHouseSecrets,
    PostgreSQLConfig,
    PostgreSQLSecrets,
    S3Config,
    S3Secrets,
    SparkConfig,
    SparkSecrets,
    decode_secret,
)

logger = logging.getLogger(__name__)


class ConnectionTestResult:
    """Result of a connection test."""

    def __init__(self, success: bool, message: str, error: str | None = None):
        self.success = success
        self.message = message
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {"success": self.success, "message": self.message}
        if self.error:
            result["error"] = self.error
        return result


class BaseConnectionTester(ABC):
    """Base class for connection testers."""

    @abstractmethod
    async def test_connection(
        self, config: dict[str, Any], secrets: dict[str, Any]
    ) -> ConnectionTestResult:
        """Test the connection and return result."""
        pass


class PostgreSQLTester(BaseConnectionTester):
    """Tester for PostgreSQL connections."""

    async def test_connection(
        self, config: dict[str, Any], secrets: dict[str, Any]
    ) -> ConnectionTestResult:
        """Test PostgreSQL connection using asyncpg."""
        try:
            import asyncpg

            pg_config = PostgreSQLConfig(**config)
            pg_secrets = PostgreSQLSecrets(**secrets)

            dsn = (
                f"postgresql://{pg_config.username}:{pg_secrets.get_password()}"
                f"@{pg_config.host}:{pg_config.port}/{pg_config.database}"
            )

            # Try to connect and ping
            conn = await asyncpg.connect(dsn)
            try:
                await conn.fetchval("SELECT 1")
                return ConnectionTestResult(
                    success=True,
                    message=f"Successfully connected to PostgreSQL at {pg_config.host}:{pg_config.port}",
                )
            finally:
                await conn.close()

        except Exception as e:
            logger.exception("PostgreSQL connection test failed")
            return ConnectionTestResult(
                success=False,
                message="Failed to connect to PostgreSQL",
                error=str(e),
            )


class ClickHouseTester(BaseConnectionTester):
    """Tester for ClickHouse connections."""

    async def test_connection(
        self, config: dict[str, Any], secrets: dict[str, Any]
    ) -> ConnectionTestResult:
        """Test ClickHouse connection using httpx (native protocol not available in async)."""
        try:
            import httpx

            ch_config = ClickHouseConfig(**config)
            ch_secrets = ClickHouseSecrets(**secrets)

            protocol = "https" if ch_config.secure else "http"
            url = f"{protocol}://{ch_config.host}:{ch_config.port}"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    auth=(ch_config.username, ch_secrets.get_password()),
                    params={"database": ch_config.database},
                    content="SELECT 1",
                    timeout=5.0,
                )
                response.raise_for_status()

                return ConnectionTestResult(
                    success=True,
                    message=f"Successfully connected to ClickHouse at {ch_config.host}:{ch_config.port}",
                )

        except Exception as e:
            logger.exception("ClickHouse connection test failed")
            return ConnectionTestResult(
                success=False,
                message="Failed to connect to ClickHouse",
                error=str(e),
            )


class S3Tester(BaseConnectionTester):
    """Tester for S3-compatible storage connections."""

    async def test_connection(
        self, config: dict[str, Any], secrets: dict[str, Any]
    ) -> ConnectionTestResult:
        """Test S3 connection using boto3."""
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError

            s3_config = S3Config(**config)
            s3_secrets = S3Secrets(**secrets)

            protocol = "https" if s3_config.use_ssl else "http"
            endpoint_url = f"{protocol}://{s3_config.endpoint}"

            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=s3_secrets.get_access_key(),
                aws_secret_access_key=s3_secrets.get_secret_key(),
                region_name=s3_config.region,
            )

            # Try to list buckets or access the default bucket
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: client.head_bucket(Bucket=s3_config.default_bucket)
                )
                return ConnectionTestResult(
                    success=True,
                    message=f"Successfully connected to S3 at {s3_config.endpoint}, bucket: {s3_config.default_bucket}",
                )
            except Exception as bucket_error:
                # If bucket doesn't exist, try to list buckets instead
                if "404" in str(bucket_error):
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: client.list_buckets()
                    )
                    return ConnectionTestResult(
                        success=True,
                        message=f"Successfully connected to S3 at {s3_config.endpoint} (bucket '{s3_config.default_bucket}' not found, but connection works)",
                    )
                raise

        except NoCredentialsError:
            return ConnectionTestResult(
                success=False,
                message="Failed to connect to S3: Invalid credentials",
                error="Invalid AWS credentials",
            )
        except Exception as e:
            logger.exception("S3 connection test failed")
            return ConnectionTestResult(
                success=False,
                message="Failed to connect to S3",
                error=str(e),
            )


class SparkTester(BaseConnectionTester):
    """Tester for Spark connections."""

    async def test_connection(
        self, config: dict[str, Any], secrets: dict[str, Any]
    ) -> ConnectionTestResult:
        """Test Spark connection by attempting to create a Spark session."""
        try:
            from pyspark.sql import SparkSession

            spark_config = SparkConfig(**config)
            SparkSecrets(**secrets)  # Validate secrets (typically empty)

            # Build Spark session configuration
            builder = SparkSession.builder.appName(spark_config.app_name)
            builder.master(spark_config.master_url)

            if spark_config.spark_home:
                builder.config("spark.home", spark_config.spark_home)

            builder.config("spark.deploy.mode", spark_config.deploy_mode)

            # Try to create session (this will test the connection)
            spark = builder.getOrCreate()

            try:
                # Test by running a simple query
                result = spark.sql("SELECT 1 as test").collect()
                if result:
                    return ConnectionTestResult(
                        success=True,
                        message=f"Successfully connected to Spark at {spark_config.master_url}",
                    )
            finally:
                spark.stop()

        except Exception as e:
            logger.exception("Spark connection test failed")
            return ConnectionTestResult(
                success=False,
                message="Failed to connect to Spark",
                error=str(e),
            )


# Import asyncio at module level for S3 tester
import asyncio


class ConnectionTestingService:
    """Service for testing connections."""

    def __init__(self):
        self.testers: dict[ConnectionType, BaseConnectionTester] = {
            ConnectionType.POSTGRES: PostgreSQLTester(),
            ConnectionType.CLICKHOUSE: ClickHouseTester(),
            ConnectionType.S3: S3Tester(),
            ConnectionType.SPARK: SparkTester(),
        }

    async def test_connection(
        self,
        connection_type: ConnectionType,
        config: dict[str, Any],
        secrets: dict[str, Any],
    ) -> ConnectionTestResult:
        """Test a connection based on its type."""
        tester = self.testers.get(connection_type)
        if not tester:
            return ConnectionTestResult(
                success=False,
                message=f"Unknown connection type: {connection_type}",
                error=f"No tester available for {connection_type}",
            )

        return await tester.test_connection(config, secrets)


# Global service instance
connection_testing_service = ConnectionTestingService()
