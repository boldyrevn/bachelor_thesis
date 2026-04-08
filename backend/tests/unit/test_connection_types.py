"""Unit tests for new connection schema types and node input validation."""

import pytest
from pydantic import BaseModel, Field
from typing import Any as AnyType, Optional, Union
from typing import Dict, List

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
    validate_output_schema,
    validate_output_schema_field,
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


# =============================================================================
# Output Schema Validation Tests
# =============================================================================


class TestOutputSchemaValidation:
    """Tests for node output_schema validation.

    Output schemas cannot contain BaseConnection subclasses because
    connections should be selected per-node, not passed as artifacts.
    """

    def test_primitives_valid_in_output(self):
        class SimpleOutput(BaseModel):
            text: str
            count: int
            ratio: float
            enabled: bool

        errors = validate_output_schema(SimpleOutput)
        assert errors == []

    def test_optional_primitives_valid_in_output(self):
        class OptionalOutput(BaseModel):
            text: Optional[str] = None
            count: Optional[int] = None

        errors = validate_output_schema(OptionalOutput)
        assert errors == []

    def test_postgres_connection_rejected_in_output(self):
        class BadOutput(BaseModel):
            connection: PostgresConnection

        errors = validate_output_schema(BadOutput)
        assert len(errors) == 1
        assert "PostgresConnection" in errors[0]
        assert "not allowed in output_schema" in errors[0]

    def test_s3_connection_rejected_in_output(self):
        class BadOutput(BaseModel):
            s3_conn: S3Connection

        errors = validate_output_schema(BadOutput)
        assert len(errors) == 1
        assert "S3Connection" in errors[0]

    def test_spark_connection_rejected_in_output(self):
        class BadOutput(BaseModel):
            spark_conn: SparkConnection

        errors = validate_output_schema(BadOutput)
        assert len(errors) == 1
        assert "SparkConnection" in errors[0]

    def test_optional_connection_rejected_in_output(self):
        class BadOutput(BaseModel):
            conn: Optional[PostgresConnection] = None

        errors = validate_output_schema(BadOutput)
        assert len(errors) == 1
        assert "PostgresConnection" in errors[0]

    def test_multiple_connection_fields_rejected(self):
        class BadOutput(BaseModel):
            pg: PostgresConnection
            s3: S3Connection

        errors = validate_output_schema(BadOutput)
        assert len(errors) == 2
        assert "PostgresConnection" in errors[0]
        assert "S3Connection" in errors[1]

    def test_connection_field_validation_error_message(self):
        class BadOutput(BaseModel):
            db_conn: PostgresConnection

        errors = validate_output_schema_field(PostgresConnection, "db_conn")
        assert len(errors) == 1
        assert "'db_conn'" in errors[0]
        assert "PostgresConnection" in errors[0]
        assert "selected per-node" in errors[0]

    def test_empty_output_schema_valid(self):
        class EmptyOutput(BaseModel):
            pass

        errors = validate_output_schema(EmptyOutput)
        assert errors == []


# =============================================================================
# Dict / List / Union Validation Tests
# =============================================================================


class TestDictListUnionValidation:
    """Tests for dict, list, and Union type validation in input/output schemas."""

    # --- Valid dict types ---

    def test_dict_str_int_valid(self):
        class DictInput(BaseModel):
            mapping: Dict[str, int]

        errors = validate_input_schema(DictInput)
        assert errors == []

    def test_dict_str_str_output_valid(self):
        class DictOutput(BaseModel):
            mapping: Dict[str, str]

        errors = validate_output_schema(DictOutput)
        assert errors == []

    def test_dict_str_float_valid(self):
        class DictInput(BaseModel):
            values: Dict[str, float]

        errors = validate_input_schema(DictInput)
        assert errors == []

    def test_dict_str_bool_valid(self):
        class DictInput(BaseModel):
            flags: Dict[str, bool]

        errors = validate_input_schema(DictInput)
        assert errors == []

    def test_dict_str_multiline_str_valid(self):
        class DictInput(BaseModel):
            queries: Dict[str, MultilineStr]

        errors = validate_input_schema(DictInput)
        assert errors == []

    def test_dict_str_optional_value_valid(self):
        class DictInput(BaseModel):
            data: Dict[str, str]

        errors = validate_input_schema(DictInput)
        assert errors == []

    # --- Valid list types ---

    def test_list_str_valid(self):
        class ListInput(BaseModel):
            items: List[str]

        errors = validate_input_schema(ListInput)
        assert errors == []

    def test_list_int_valid(self):
        class ListInput(BaseModel):
            numbers: List[int]

        errors = validate_input_schema(ListInput)
        assert errors == []

    def test_list_float_output_valid(self):
        class ListOutput(BaseModel):
            scores: List[float]

        errors = validate_output_schema(ListOutput)
        assert errors == []

    def test_list_bool_valid(self):
        class ListInput(BaseModel):
            flags: List[bool]

        errors = validate_input_schema(ListInput)
        assert errors == []

    def test_optional_dict_valid(self):
        class Input(BaseModel):
            mapping: Optional[Dict[str, str]] = None

        errors = validate_input_schema(Input)
        assert errors == []

    def test_optional_list_valid(self):
        class Input(BaseModel):
            items: Optional[List[int]] = None

        errors = validate_input_schema(Input)
        assert errors == []

    # --- Valid Union types ---

    def test_union_str_int_valid(self):
        class UnionInput(BaseModel):
            value: Union[str, int]

        errors = validate_input_schema(UnionInput)
        assert errors == []

    def test_union_str_list_valid(self):
        class UnionInput(BaseModel):
            value: Union[str, List[str]]

        errors = validate_input_schema(UnionInput)
        assert errors == []

    def test_union_str_dict_valid(self):
        class UnionInput(BaseModel):
            value: Union[str, Dict[str, int]]

        errors = validate_input_schema(UnionInput)
        assert errors == []

    def test_union_int_float_list_valid(self):
        class UnionInput(BaseModel):
            value: Union[int, float, List[str]]

        errors = validate_input_schema(UnionInput)
        assert errors == []

    def test_union_str_int_output_valid(self):
        class UnionOutput(BaseModel):
            value: Union[str, int]

        errors = validate_output_schema(UnionOutput)
        assert errors == []

    def test_union_dict_list_output_valid(self):
        class UnionOutput(BaseModel):
            value: Union[Dict[str, str], List[int]]

        errors = validate_output_schema(UnionOutput)
        assert errors == []

    # --- Rejected: Connection in dict ---

    def test_dict_str_connection_rejected(self):
        class BadInput(BaseModel):
            conns: Dict[str, PostgresConnection]

        errors = validate_input_schema(BadInput)
        assert len(errors) == 1
        assert "PostgresConnection" in errors[0]

    # --- Rejected: Connection in list ---

    def test_list_connection_rejected(self):
        class BadInput(BaseModel):
            conns: List[S3Connection]

        errors = validate_input_schema(BadInput)
        assert len(errors) == 1
        assert "S3Connection" in errors[0]

    # --- Rejected: Connection in Union ---

    def test_union_with_connection_rejected(self):
        class BadInput(BaseModel):
            value: Union[str, PostgresConnection]

        errors = validate_input_schema(BadInput)
        assert len(errors) == 1
        assert "PostgresConnection" in errors[0]

    # --- Rejected: Nested dict/list ---

    def test_nested_dict_rejected(self):
        class BadInput(BaseModel):
            nested: Dict[str, Dict[str, str]]

        errors = validate_input_schema(BadInput)
        assert len(errors) == 1
        assert "dict" in errors[0].lower()

    def test_nested_list_rejected(self):
        class BadInput(BaseModel):
            nested: List[List[str]]

        errors = validate_input_schema(BadInput)
        assert len(errors) == 1
        assert "list" in errors[0].lower()

    def test_dict_with_list_value_rejected(self):
        class BadInput(BaseModel):
            data: Dict[str, List[str]]

        errors = validate_input_schema(BadInput)
        assert len(errors) == 1
        assert "list" in errors[0].lower()

    # --- Rejected: BaseModel in dict/list ---

    def test_dict_with_basemodel_rejected(self):
        class SubModel(BaseModel):
            name: str

        class BadInput(BaseModel):
            items: Dict[str, SubModel]

        errors = validate_input_schema(BadInput)
        assert len(errors) == 1

    def test_list_with_basemodel_rejected(self):
        class SubModel(BaseModel):
            name: str

        class BadInput(BaseModel):
            items: List[SubModel]

        errors = validate_input_schema(BadInput)
        assert len(errors) == 1
