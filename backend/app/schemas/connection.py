"""Pydantic schemas for connection configuration and secrets."""

import base64
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Encryption Helpers (MVP - Base64 encoding)
# =============================================================================


def encode_secret(value: str) -> str:
    """Encode a secret value using base64 (MVP encryption)."""
    return base64.b64encode(value.encode()).decode()


def decode_secret(value: str) -> str:
    """Decode a base64-encoded secret."""
    return base64.b64decode(value.encode()).decode()


# =============================================================================
# Connection Type-Specific Configs
# =============================================================================


class PostgreSQLConfig(BaseModel):
    """PostgreSQL connection configuration."""

    host: str = Field(..., description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")

    class Config:
        json_schema_extra = {
            "example": {
                "host": "localhost",
                "port": 5432,
                "database": "mydb",
                "username": "user",
            }
        }


class PostgreSQLSecrets(BaseModel):
    """PostgreSQL connection secrets."""

    password: str = Field(..., description="Database password")

    @field_validator("password", mode="before")
    @classmethod
    def encode_password(cls, v: str) -> str:
        """Encode password if not already encoded."""
        if not v.startswith("base64:"):
            return f"base64:{encode_secret(v)}"
        return v

    def get_password(self) -> str:
        """Get decoded password."""
        if self.password.startswith("base64:"):
            return decode_secret(self.password[7:])
        return self.password


class ClickHouseConfig(BaseModel):
    """ClickHouse connection configuration."""

    host: str = Field(..., description="ClickHouse host")
    port: int = Field(default=8123, ge=1, le=65535, description="HTTP port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Username")


class ClickHouseSecrets(BaseModel):
    """ClickHouse connection secrets."""

    password: str = Field(..., description="Password")

    @field_validator("password", mode="before")
    @classmethod
    def encode_password(cls, v: str) -> str:
        """Encode password if not already encoded."""
        if not v.startswith("base64:"):
            return f"base64:{encode_secret(v)}"
        return v

    def get_password(self) -> str:
        """Get decoded password."""
        if self.password.startswith("base64:"):
            return decode_secret(self.password[7:])
        return self.password


class S3Config(BaseModel):
    """S3-compatible storage connection configuration."""

    endpoint: str = Field(..., description="S3 endpoint URL")
    region: str = Field(default="us-east-1", description="AWS region")
    default_bucket: str = Field(..., description="Default bucket name")
    use_ssl: bool = Field(default=True, description="Use SSL for connection")

    class Config:
        json_schema_extra = {
            "example": {
                "endpoint": "s3.amazonaws.com",
                "region": "us-east-1",
                "default_bucket": "my-bucket",
                "use_ssl": True,
            }
        }


class S3Secrets(BaseModel):
    """S3 connection secrets."""

    access_key: str = Field(..., description="AWS Access Key ID")
    secret_key: str = Field(..., description="AWS Secret Access Key")

    @field_validator("access_key", "secret_key", mode="before")
    @classmethod
    def encode_keys(cls, v: str) -> str:
        """Encode secret if not already encoded."""
        if not v.startswith("base64:"):
            return f"base64:{encode_secret(v)}"
        return v

    def get_access_key(self) -> str:
        """Get decoded access key."""
        if self.access_key.startswith("base64:"):
            return decode_secret(self.access_key[7:])
        return self.access_key

    def get_secret_key(self) -> str:
        """Get decoded secret key."""
        if self.secret_key.startswith("base64:"):
            return decode_secret(self.secret_key[7:])
        return self.secret_key


class SparkConfig(BaseModel):
    """Spark connection configuration."""

    master_url: str = Field(..., description="Spark master URL")
    app_name: str = Field(default="FlowForge", description="Application name")
    spark_home: Optional[str] = Field(default=None, description="SPARK_HOME path")
    deploy_mode: Literal["client", "cluster"] = Field(
        default="client", description="Deploy mode"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "master_url": "spark://localhost:7077",
                "app_name": "FlowForge",
                "deploy_mode": "client",
            }
        }


class SparkSecrets(BaseModel):
    """Spark connection secrets (typically empty for standalone)."""

    pass


# =============================================================================
# Helper Functions
# =============================================================================


def validate_connection_config(
    connection_type: str, config: dict[str, Any], secrets: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Validate connection configuration and secrets based on type.

    Returns encoded config and secrets ready for storage.
    """
    if connection_type == "postgres":
        config_model = PostgreSQLConfig(**config)
        secrets_model = PostgreSQLSecrets(**secrets)
        return config_model.model_dump(), secrets_model.model_dump()

    elif connection_type == "clickhouse":
        config_model = ClickHouseConfig(**config)
        secrets_model = ClickHouseSecrets(**secrets)
        return config_model.model_dump(), secrets_model.model_dump()

    elif connection_type == "s3":
        config_model = S3Config(**config)
        secrets_model = S3Secrets(**secrets)
        return config_model.model_dump(), secrets_model.model_dump()

    elif connection_type == "spark":
        config_model = SparkConfig(**config)
        secrets_model = SparkSecrets(**secrets)
        return config_model.model_dump(), secrets_model.model_dump()

    else:
        raise ValueError(f"Unknown connection type: {connection_type}")
