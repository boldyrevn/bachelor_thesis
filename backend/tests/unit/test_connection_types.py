"""Unit tests for new connection schema types and node input validation."""

import pytest
from pydantic import BaseModel, Field
from typing import Any as AnyType, Optional

from app.schemas.connection import (
    Secret,
    BaseConnection,
    PostgresConnection,
    ClickHouseConnection,
    S3Connection,
    SparkConnection,
    get_connection_class,
    assemble_connection,
    CONNECTION_CLASSES,
)
from app.schemas.node_types import MultilineStr
from app.schemas.node_input_validation import (
    validate_field_type,
    validate_input_schema,
)


# =============================================================================
# Secret Tests
# =============================================================================


class TestSecret:
    """Tests for the Secret wrapper."""

    def test_encode_and_decode(self):
        secret = Secret("my_password")
        assert secret.get_value() == "my_password"

    def test_already_encoded(self):
        secret = Secret("base64:cGFzc3dvcmQ=")
        assert secret.get_value() == "password"

    def test_serialize(self):
        secret = Secret("test")
        serialized = secret.serialize()
        assert serialized.startswith("base64:")

    def test_from_encoded(self):
        instance = Secret.from_encoded("base64:aGVsbG8=")
        assert instance.get_value() == "hello"

    def test_repr_masks_secret(self):
        secret = Secret("super_secret")
        assert "********" in repr(secret)
        assert "super_secret" not in repr(secret)

    def test_empty_secret(self):
        secret = Secret()
        assert secret.get_value() == ""

    def test_equality(self):
        s1 = Secret("same")
        s2 = Secret("same")
        assert s1 == s2

    def test_inequality(self):
        s1 = Secret("one")
        s2 = Secret("two")
        assert s1 != s2


# =============================================================================
# Connection Class Tests
# =============================================================================


class TestPostgresConnection:
    """Tests for PostgresConnection."""

    def test_connection_type(self):
        assert PostgresConnection.connection_type() == "postgres"

    def test_json_schema_has_marker(self):
        schema = PostgresConnection.model_json_schema()
        assert schema.get("x-connection-type") == "postgres"

    def test_secret_fields_in_schema(self):
        schema = PostgresConnection.model_json_schema()
        assert "password" in schema["properties"]

    def test_split_for_db(self):
        conn = PostgresConnection(
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password=Secret("pass123"),
        )
        config, secrets = conn.split_for_db()

        assert "password" not in config
        assert "host" not in secrets
        assert "password" in secrets
        assert secrets["password"].startswith("base64:")

    def test_from_db_and_roundtrip(self):
        config = {"host": "localhost", "port": 5432, "database": "db", "username": "u"}
        secrets = {"password": "base64:cGFzcw=="}  # "pass"

        conn = PostgresConnection.from_db(config, secrets)
        assert conn.host == "localhost"
        assert conn.password.get_value() == "pass"


class TestS3Connection:
    """Tests for S3Connection."""

    def test_connection_type(self):
        assert S3Connection.connection_type() == "s3"

    def test_json_schema_has_marker(self):
        schema = S3Connection.model_json_schema()
        assert schema.get("x-connection-type") == "s3"

    def test_split_for_db(self):
        conn = S3Connection(
            endpoint="s3.amazonaws.com",
            region="us-east-1",
            default_bucket="my-bucket",
            access_key=Secret("AKIAIOSFODNN7EXAMPLE"),
            secret_key=Secret("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
        )
        config, secrets = conn.split_for_db()

        assert "access_key" not in config
        assert "secret_key" not in config
        assert "endpoint" not in secrets
        assert len(secrets) == 2

    def test_no_secrets_spark(self):
        conn = SparkConnection(
            master_url="spark://localhost:7077",
            app_name="TestApp",
        )
        config, secrets = conn.split_for_db()
        assert len(secrets) == 0  # Spark has no secrets


class TestConnectionRegistry:
    """Tests for connection class registry."""

    def test_all_types_registered(self):
        assert set(CONNECTION_CLASSES.keys()) == {
            "postgres",
            "clickhouse",
            "s3",
            "spark",
        }

    def test_get_connection_class(self):
        assert get_connection_class("postgres") == PostgresConnection
        assert get_connection_class("s3") == S3Connection

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown connection type"):
            get_connection_class("redis")

    def test_assemble_connection(self):
        config = {"host": "localhost", "port": 5432, "database": "db", "username": "u"}
        secrets = {"password": "base64:cGFzcw=="}

        conn = assemble_connection("postgres", config, secrets)
        assert isinstance(conn, PostgresConnection)
        assert conn.host == "localhost"


class TestMultilineStr:
    """Tests for MultilineStr type."""

    def test_is_string(self):
        # MultilineStr should behave like str at runtime
        value: MultilineStr = "hello\nworld"
        assert isinstance(value, str)

    def test_json_schema_has_multiline_format(self):
        class TestInput(BaseModel):
            query: MultilineStr = Field(description="SQL query")

        schema = TestInput.model_json_schema()
        assert schema["properties"]["query"].get("format") == "multiline"
        assert schema["properties"]["query"]["description"] == "SQL query"

    def test_optional_multiline_str(self):
        class TestInput(BaseModel):
            query: Optional[MultilineStr] = None

        schema = TestInput.model_json_schema()
        # Should still produce multiline format for the inner type
        props = schema.get("properties", {})
        if "query" in props:
            query_prop = props["query"]
            # Pydantic may represent Optional differently, check for anyOf
            if "anyOf" in query_prop:
                has_multiline = any(
                    item.get("format") == "multiline" for item in query_prop["anyOf"]
                )
                assert has_multiline


# =============================================================================
# Input Schema Validation Tests
# =============================================================================


class ValidInput(BaseModel):
    name: str
    count: int
    ratio: float
    enabled: bool
    query: MultilineStr = Field(description="A multiline query")


class NestedInput(BaseModel):
    host: str = Field(description="Host")
    port: int = Field(description="Port")


class ValidWithNested(BaseModel):
    text: str
    optional_host: Optional[str] = None
    pg_connection: PostgresConnection


class TestInputSchemaValidation:
    """Tests for node input_schema type validation."""

    def test_valid_primitives(self):
        errors = validate_input_schema(ValidInput)
        assert errors == []

    def test_valid_without_nested(self):
        errors = validate_input_schema(ValidWithNested)
        assert errors == []

    def test_disallowed_type(self):
        # Test directly via validate_field_type since Pydantic won't
        # allow non-model classes as field types
        class NotAModel:
            pass

        errors = validate_field_type(NotAModel, "thing")
        assert len(errors) > 0
        assert "thing" in errors[0]

    def test_optional_primitive_valid(self):
        class OptionalInput(BaseModel):
            name: Optional[str] = None

        errors = validate_input_schema(OptionalInput)
        assert errors == []

    def test_connection_field_valid(self):
        class ConnInput(BaseModel):
            pg: PostgresConnection
            s3: S3Connection

        errors = validate_input_schema(ConnInput)
        assert errors == []

    def test_empty_schema_valid(self):
        class EmptyInput(BaseModel):
            pass

        errors = validate_input_schema(EmptyInput)
        assert errors == []
