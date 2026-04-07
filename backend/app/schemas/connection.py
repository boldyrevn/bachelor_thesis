"""Connection schemas with typed classes, Secret fields, and test methods."""

import base64
import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Literal, Optional, Self

from pydantic import BaseModel, ConfigDict, Field, GetJsonSchemaHandler, field_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

logger = logging.getLogger(__name__)


# =============================================================================
# Secret Wrapper
# =============================================================================


class Secret:
    """Wrapper for secret string values.

    Stores value as base64-encoded string for persistence,
    decodes only when explicitly requested via get_value().
    """

    def __init__(self, value: str = ""):
        self._encoded = (
            self._encode(value) if value and not value.startswith("base64:") else value
        )

    @staticmethod
    def _encode(value: str) -> str:
        return f"base64:{base64.b64encode(value.encode()).decode()}"

    @staticmethod
    def _decode(encoded: str) -> str:
        if encoded.startswith("base64:"):
            return base64.b64decode(encoded[7:]).decode()
        return encoded

    def get_value(self) -> str:
        """Return the decoded secret value."""
        return self._decode(self._encoded)

    def __repr__(self) -> str:
        return "Secret('********')"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Secret):
            return self._encoded == other._encoded
        return False

    def __hash__(self) -> int:
        return hash(self._encoded)

    def serialize(self) -> str:
        """Return the encoded representation for DB storage."""
        return self._encoded

    @classmethod
    def from_encoded(cls, encoded: str) -> "Secret":
        """Create from an already-encoded value."""
        instance = cls.__new__(cls)
        instance._encoded = encoded
        return instance

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Any
    ) -> core_schema.CoreSchema:
        """Tell Pydantic how to validate and serialize Secret."""
        return core_schema.no_info_plain_validator_function(
            lambda v: wrap_secret(v) if not isinstance(v, Secret) else v,
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: Any, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Tell Pydantic to represent Secret as a string in JSON schema."""
        return {
            "type": "string",
            "description": "Secret value (base64-encoded for storage)",
        }


# =============================================================================
# Secret Field Validator
# =============================================================================


def wrap_secret(value: Any) -> Secret:
    """Wrap a value in Secret if it's a string, pass through if already Secret."""
    if isinstance(value, Secret):
        return value
    if isinstance(value, str):
        return Secret(value)
    raise ValueError(f"Expected str or Secret, got {type(value).__name__}")


# =============================================================================
# Base Connection
# =============================================================================


class BaseConnection(BaseModel, ABC):
    """Base class for all typed connections.

    Subclasses must:
    1. Define typed fields (host, port, etc.)
    2. Implement async test() method
    3. Set model_config with json_schema_extra={"x-connection-type": "<type>"}
    4. Add field_validator for each secret field using wrap_secret

    Usage:
        conn = PostgresConnection.from_db(config, secrets)
        result = await conn.test()
    """

    SECRET_FIELDS: ClassVar[set[str]] = set()

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    @classmethod
    @abstractmethod
    def connection_type(cls) -> str:
        """Return the connection type identifier (e.g. 'postgres')."""
        ...

    @abstractmethod
    async def test(self) -> tuple[bool, str, str | None]:
        """Test this connection.

        Returns:
            (success, message, error)
        """
        ...

    @classmethod
    def from_db(cls, config: dict[str, Any], secrets: dict[str, Any]) -> Self:
        """Assemble a connection instance from DB config + secrets dicts.

        Wraps secret field values in Secret() before constructing.
        """
        merged = {**config, **secrets}
        secret_fields = getattr(cls, "SECRET_FIELDS", set())
        for field_name in secret_fields:
            if field_name in merged and not isinstance(merged[field_name], Secret):
                merged[field_name] = wrap_secret(merged[field_name])
        return cls(**merged)

    def split_for_db(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Split instance into (config_dict, secrets_dict) for DB storage.

        Uses SECRET_FIELDS class attribute to determine which fields are secrets.
        """
        secret_fields: set[str] = getattr(self, "SECRET_FIELDS", set())
        config = {}
        secrets = {}
        for field_name in self.model_fields_set | set(self.model_fields.keys()):
            value = getattr(self, field_name, None)
            if value is None:
                continue
            if field_name in secret_fields:
                if isinstance(value, Secret):
                    secrets[field_name] = value.serialize()
                else:
                    secrets[field_name] = value
            else:
                config[field_name] = value
        return config, secrets


# =============================================================================
# PostgreSQL Connection
# =============================================================================


class PostgresConnection(BaseConnection):
    """PostgreSQL database connection."""

    model_config = ConfigDict(
        json_schema_extra={"x-connection-type": "postgres"},
    )

    SECRET_FIELDS: ClassVar[set[str]] = {"password"}

    host: str = Field(..., description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: Secret = Field(..., description="Database password")

    _wrap_password = field_validator("password", mode="before")(wrap_secret)

    @classmethod
    def connection_type(cls) -> str:
        return "postgres"

    async def test(self) -> tuple[bool, str, str | None]:
        """Test PostgreSQL connection using asyncpg."""
        try:
            import asyncpg

            dsn = (
                f"postgresql://{self.username}:{self.password.get_value()}"
                f"@{self.host}:{self.port}/{self.database}"
            )
            logger.info(f"Connection dsn: {dsn}")

            conn = await asyncpg.connect(dsn)
            try:
                await conn.fetchval("SELECT 1")
                return (
                    True,
                    f"Successfully connected to PostgreSQL at {self.host}:{self.port}",
                    None,
                )
            finally:
                await conn.close()

        except Exception as e:
            logger.exception("PostgreSQL connection test failed")
            return False, "Failed to connect to PostgreSQL", str(e)


# =============================================================================
# ClickHouse Connection
# =============================================================================


class ClickHouseConnection(BaseConnection):
    """ClickHouse database connection."""

    model_config = ConfigDict(
        json_schema_extra={"x-connection-type": "clickhouse"},
    )

    SECRET_FIELDS: ClassVar[set[str]] = {"password"}

    host: str = Field(..., description="ClickHouse host")
    port: int = Field(default=8123, ge=1, le=65535, description="HTTP port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Username")
    password: Secret = Field(..., description="Password")

    _wrap_password = field_validator("password", mode="before")(wrap_secret)

    @classmethod
    def connection_type(cls) -> str:
        return "clickhouse"

    async def test(self) -> tuple[bool, str, str | None]:
        """Test ClickHouse connection via HTTP API."""
        try:
            import httpx

            protocol = "http"
            url = f"{protocol}://{self.host}:{self.port}"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    auth=(self.username, self.password.get_value()),
                    params={"database": self.database},
                    content="SELECT 1",
                    timeout=5.0,
                )
                response.raise_for_status()

                return (
                    True,
                    f"Successfully connected to ClickHouse at {self.host}:{self.port}",
                    None,
                )

        except Exception as e:
            logger.exception("ClickHouse connection test failed")
            return False, "Failed to connect to ClickHouse", str(e)


# =============================================================================
# S3 Connection
# =============================================================================


class S3Connection(BaseConnection):
    """S3-compatible storage connection."""

    model_config = ConfigDict(
        json_schema_extra={"x-connection-type": "s3"},
    )

    SECRET_FIELDS: ClassVar[set[str]] = {"access_key", "secret_key"}

    endpoint: str = Field(..., description="S3 endpoint URL")
    region: str = Field(default="us-east-1", description="AWS region")
    default_bucket: str = Field(..., description="Default bucket name")
    use_ssl: bool = Field(default=True, description="Use SSL for connection")
    access_key: Secret = Field(..., description="AWS Access Key ID")
    secret_key: Secret = Field(..., description="AWS Secret Access Key")

    _wrap_access_key = field_validator("access_key", mode="before")(wrap_secret)
    _wrap_secret_key = field_validator("secret_key", mode="before")(wrap_secret)

    @classmethod
    def connection_type(cls) -> str:
        return "s3"

    async def test(self) -> tuple[bool, str, str | None]:
        """Test S3 connection using boto3."""
        import asyncio

        try:
            import boto3
            from botocore.exceptions import NoCredentialsError

            protocol = "https" if self.use_ssl else "http"
            endpoint_url = f"{protocol}://{self.endpoint}"

            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=self.access_key.get_value(),
                aws_secret_access_key=self.secret_key.get_value(),
                region_name=self.region,
            )

            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: client.head_bucket(Bucket=self.default_bucket)
                )
                return (
                    True,
                    f"Successfully connected to S3 at {self.endpoint}, bucket: {self.default_bucket}",
                    None,
                )
            except Exception as bucket_error:
                if "404" in str(bucket_error):
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: client.list_buckets()
                    )
                    return (
                        True,
                        f"Successfully connected to S3 at {self.endpoint} (bucket '{self.default_bucket}' not found, but connection works)",
                        None,
                    )
                raise

        except NoCredentialsError:
            return (
                False,
                "Failed to connect to S3: Invalid credentials",
                "Invalid AWS credentials",
            )
        except Exception as e:
            logger.exception("S3 connection test failed")
            return False, "Failed to connect to S3", str(e)


# =============================================================================
# Spark Connection
# =============================================================================


class SparkConnection(BaseConnection):
    """Apache Spark cluster connection."""

    model_config = ConfigDict(
        json_schema_extra={"x-connection-type": "spark"},
    )

    SECRET_FIELDS: ClassVar[set[str]] = set()

    master_url: str = Field(..., description="Spark master URL")
    app_name: str = Field(default="FlowForge", description="Application name")
    spark_home: Optional[str] = Field(default=None, description="SPARK_HOME path")
    deploy_mode: Literal["client", "cluster"] = Field(
        default="client", description="Deploy mode"
    )

    @classmethod
    def connection_type(cls) -> str:
        return "spark"

    async def test(self) -> tuple[bool, str, str | None]:
        """Test Spark connection by running a simple query."""
        try:
            from pyspark.sql import SparkSession

            builder = SparkSession.builder.appName(self.app_name)
            builder.master(self.master_url)

            if self.spark_home:
                builder.config("spark.home", self.spark_home)

            builder.config("spark.deploy.mode", self.deploy_mode)

            spark = builder.getOrCreate()
            try:
                result = spark.sql("SELECT 1 as test").collect()
                if result:
                    return (
                        True,
                        f"Successfully connected to Spark at {self.master_url}",
                        None,
                    )
                return False, "Spark query returned empty result", None
            finally:
                spark.stop()

        except Exception as e:
            logger.exception("Spark connection test failed")
            return False, "Failed to connect to Spark", str(e)


# =============================================================================
# Connection Type Registry
# =============================================================================

CONNECTION_CLASSES: dict[str, type[BaseConnection]] = {
    "postgres": PostgresConnection,
    "clickhouse": ClickHouseConnection,
    "s3": S3Connection,
    "spark": SparkConnection,
}


def get_connection_class(connection_type: str) -> type[BaseConnection]:
    """Get a connection class by type identifier.

    Args:
        connection_type: One of 'postgres', 'clickhouse', 's3', 'spark'

    Returns:
        The corresponding connection class

    Raises:
        ValueError: If connection type is unknown
    """
    cls = CONNECTION_CLASSES.get(connection_type)
    if cls is None:
        raise ValueError(f"Unknown connection type: {connection_type}")
    return cls


# =============================================================================
# Helper: assemble connection from DB row
# =============================================================================


def assemble_connection(
    connection_type: str, config: dict[str, Any], secrets: dict[str, Any]
) -> BaseConnection:
    """Create a typed connection instance from DB config + secrets.

    Args:
        connection_type: Type identifier
        config: Configuration dict from DB
        secrets: Secrets dict from DB

    Returns:
        Typed BaseConnection instance
    """
    cls = get_connection_class(connection_type)
    return cls.from_db(config, secrets)
