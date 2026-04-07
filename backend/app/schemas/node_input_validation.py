"""Validation utilities for node input/output schemas.

Only the following types are allowed in node input_schema fields:
- Primitives: str, int, float, bool
- Custom strings: MultilineStr, DateStr, DateTimeStr
- BaseConnection subclasses (PostgresConnection, S3Connection, etc.)
- Optional[T] where T is any of the above

Nested BaseModel is NOT allowed.
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

    # Check for Field with format in metadata
    for meta in args[1:]:
        if hasattr(meta, "json_schema_extra") and isinstance(
            meta.json_schema_extra, dict
        ):
            fmt = meta.json_schema_extra.get(_FORMAT_KEY)
            if fmt in _ALLOWED_FORMATS:
                return True
    return False


def _is_optional(annotation: Any) -> tuple[bool, Any]:
    """Check if annotation is Optional[T] and return the inner type."""
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        # Optional[T] is Union[T, None]
        if len(args) == 2 and type(None) in args:
            inner = args[0] if args[1] is type(None) else args[1]
            return True, inner
    return False, annotation


def validate_field_type(annotation: Any, field_name: str) -> list[str]:
    """Validate that a field annotation is an allowed node input type.

    Allowed types:
    - Primitives: str, int, float, bool
    - Custom strings: MultilineStr, DateStr, DateTimeStr
    - BaseConnection subclasses (PostgresConnection, S3Connection, etc.)
    - Optional[T] where T is any of the above

    Args:
        annotation: The field type annotation
        field_name: Field name for error messages

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    # Unwrap Optional
    is_opt, inner_type = _is_optional(annotation)
    if is_opt:
        annotation = inner_type

    # Check primitives
    if annotation in _PRIMITIVE_TYPES:
        return errors

    # Check custom string types (MultilineStr, DateStr, DateTimeStr)
    if _is_custom_str(annotation):
        return errors

    # Check connection types
    if _is_connection_type(annotation):
        return errors

    # Not allowed
    type_name = getattr(annotation, "__name__", str(annotation))
    errors.append(
        f"Field '{field_name}' has disallowed type '{type_name}'. "
        f"Allowed: str, int, float, bool, MultilineStr, DateStr, "
        f"DateTimeStr, BaseConnection subclasses"
    )
    return errors


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
