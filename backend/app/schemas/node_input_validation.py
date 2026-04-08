"""Validation utilities for node input/output schemas.

Input schema allowed types:
- Primitives: str, int, float, bool
- Custom strings: MultilineStr, DateStr, DateTimeStr
- BaseConnection subclasses (PostgresConnection, S3Connection, etc.) — direct fields only
- dict[str, T] — T = simple types (primitives, custom strings)
- list[T] — T = simple types
- Union[T1, T2, ...] — Ti = simple types, dict, list (no Connection in Union)
- Optional[T] — T = simple types, dict, list

Output schema allowed types:
- Same as input, but BaseConnection subclasses are FORBIDDEN.

Nested BaseModel is NOT allowed in either schema.
"""

import logging
from typing import Annotated, Any, get_args, get_origin

from pydantic import BaseModel

from app.schemas.connection import BaseConnection

logger = logging.getLogger(__name__)

# Allowed primitive Python types
_PRIMITIVE_TYPES = {str, int, float, bool}

# Allowed format markers (Annotated[str, Field(format='...')])
_ALLOWED_FORMATS = {"multiline", "date", "date-time"}

# The annotation marker key
_FORMAT_KEY = "format"


# =============================================================================
# Type checking helpers
# =============================================================================


def _is_connection_type(annotation: Any) -> bool:
    """Check if an annotation is a BaseConnection subclass."""
    try:
        return isinstance(annotation, type) and issubclass(annotation, BaseConnection)
    except TypeError:
        return False


def _is_custom_str(annotation: Any) -> bool:
    """Check if annotation is MultilineStr, DateStr, or DateTimeStr."""
    origin = get_origin(annotation)
    if origin is not Annotated:
        return False

    args = get_args(annotation)
    if not args or args[0] is not str:
        return False

    for meta in args[1:]:
        if hasattr(meta, "json_schema_extra") and isinstance(
            meta.json_schema_extra, dict
        ):
            fmt = meta.json_schema_extra.get(_FORMAT_KEY)
            if fmt in _ALLOWED_FORMATS:
                return True
    return False


def _is_simple_type(annotation: Any) -> bool:
    """Check if annotation is a simple allowed leaf type (primitive or custom string).

    These are the types allowed as dict values and list items.
    """
    if annotation in _PRIMITIVE_TYPES:
        return True
    if _is_custom_str(annotation):
        return True
    return False


# =============================================================================
# Core validation logic
# =============================================================================


def _validate_value_type(annotation: Any, field_name: str) -> list[str]:
    """Validate a type that appears as a dict value or list item.

    Only simple types (primitives, custom strings) are allowed here.
    No Connection, no BaseModel, no nested dict/list.
    """
    if _is_simple_type(annotation):
        return []

    type_name = getattr(annotation, "__name__", str(annotation))
    return [
        f"Field '{field_name}' has disallowed container value type '{type_name}'. "
        f"dict/list values must be primitives or custom strings "
        f"(str, int, float, bool, MultilineStr, DateStr, DateTimeStr)."
    ]


def _validate_type(
    annotation: Any, field_name: str, allow_connections: bool
) -> list[str]:
    """Recursively validate a field type annotation.

    Args:
        annotation: The field type annotation
        field_name: Field name for error messages
        allow_connections: If True, allow BaseConnection as a direct field type
                          (input_schema). If False, reject all connections
                          (output_schema, and types inside dict/list/Union).

    Returns:
        List of error messages (empty if valid)
    """
    origin = get_origin(annotation)

    # --- Simple leaf types ---
    if _is_simple_type(annotation):
        return []

    # --- BaseConnection ---
    if _is_connection_type(annotation):
        if allow_connections:
            return []
        conn_name = getattr(annotation, "__name__", str(annotation))
        return [
            f"Field '{field_name}' uses '{conn_name}' which is not allowed in "
            f"output_schema. Connections must be selected per-node in the UI, "
            f"not passed as artifacts between nodes."
        ]

    # --- dict[str, T] ---
    if origin is dict:
        args = get_args(annotation)
        if len(args) != 2:
            return [
                f"Field '{field_name}' uses 'dict' without type parameters. "
                f"Use dict[str, <type>] instead."
            ]
        key_type, value_type = args
        if key_type is not str:
            return [
                f"Field '{field_name}' uses 'dict' with non-string keys. "
                f"Only dict[str, <type>] is allowed."
            ]
        return _validate_value_type(value_type, field_name)

    # --- list[T] ---
    if origin is list:
        args = get_args(annotation)
        if not args:
            return [
                f"Field '{field_name}' uses 'list' without type parameters. "
                f"Use list[<type>] instead."
            ]
        item_type = args[0]
        return _validate_value_type(item_type, field_name)

    # --- Union[T1, T2, ...] (includes Optional[T] = Union[T, None]) ---
    if origin is not None:
        # Union type: validate each member
        args = get_args(annotation)
        all_errors: list[str] = []
        for member in args:
            if member is type(None):
                continue  # None in Union/Optional is always fine
            member_errors = _validate_type(member, field_name, allow_connections=False)
            all_errors.extend(member_errors)
        return all_errors

    # --- Everything else (BaseModel, custom classes, etc.) ---
    type_name = getattr(annotation, "__name__", str(annotation))
    return [
        f"Field '{field_name}' has disallowed type '{type_name}'. "
        f"Allowed: str, int, float, bool, MultilineStr, DateStr, DateTimeStr, "
        f"BaseConnection (input only), dict[str, T], list[T], Union[...]."
    ]


# =============================================================================
# Public API: validate full schemas
# =============================================================================


def validate_field_type(annotation: Any, field_name: str) -> list[str]:
    """Validate that a field annotation is an allowed node input type.

    Args:
        annotation: The field type annotation
        field_name: Field name for error messages

    Returns:
        List of error messages (empty if valid)
    """
    return _validate_type(annotation, field_name, allow_connections=True)


def validate_input_schema(schema_class: type[BaseModel]) -> list[str]:
    """Validate that a node input schema only uses allowed field types.

    Args:
        schema_class: Pydantic BaseModel class to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    for field_name, field_info in schema_class.model_fields.items():
        annotation = field_info.annotation
        if annotation is None:
            errors.append(f"Field '{field_name}' has no type annotation")
            continue

        field_errors = validate_field_type(annotation, field_name)
        errors.extend(field_errors)

    return errors


def validate_output_schema_field(annotation: Any, field_name: str) -> list[str]:
    """Validate that a field is allowed in output_schema.

    Args:
        annotation: The field type annotation
        field_name: Field name for error messages

    Returns:
        List of error messages (empty if valid)
    """
    return _validate_type(annotation, field_name, allow_connections=False)


def validate_output_schema(schema_class: type[BaseModel]) -> list[str]:
    """Validate that a node output schema does not contain forbidden fields.

    Args:
        schema_class: Pydantic BaseModel class to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    for field_name, field_info in schema_class.model_fields.items():
        annotation = field_info.annotation
        if annotation is None:
            errors.append(f"Field '{field_name}' has no type annotation")
            continue

        field_errors = validate_output_schema_field(annotation, field_name)
        errors.extend(field_errors)

    return errors
