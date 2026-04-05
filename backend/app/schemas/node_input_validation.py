"""Validation utilities for node input/output schemas."""

import logging
from typing import Annotated, Any, get_args, get_origin

from pydantic import BaseModel

from app.schemas.connection import BaseConnection

logger = logging.getLogger(__name__)

# Allowed primitive Python types
_PRIMITIVE_TYPES = {str, int, float, bool, type(None)}

# The MultilineStr annotation marker (we detect by json_schema_extra format)
_MULTILINE_FORMAT_KEY = "format"
_MULTILINE_FORMAT_VALUE = "multiline"


def _is_connection_type(annotation: Any) -> bool:
    """Check if an annotation is a BaseConnection subclass."""
    # Handle direct subclass references
    try:
        return isinstance(annotation, type) and issubclass(annotation, BaseConnection)
    except TypeError:
        return False


def _is_multiline_str(annotation: Any) -> bool:
    """Check if annotation is MultilineStr (Annotated[str, Field(format='multiline')])."""
    origin = get_origin(annotation)
    if origin is not Annotated:
        return False

    args = get_args(annotation)
    if not args or args[0] is not str:
        return False

    # Check for Field with format='multiline' in metadata
    for meta in args[1:]:
        if hasattr(meta, "json_schema_extra") and isinstance(
            meta.json_schema_extra, dict
        ):
            if (
                meta.json_schema_extra.get(_MULTILINE_FORMAT_KEY)
                == _MULTILINE_FORMAT_VALUE
            ):
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
    - MultilineStr (Annotated[str, Field(format='multiline')])
    - BaseConnection subclasses (PostgresConnection, S3Connection, etc.)
    - Nested Pydantic BaseModel (recursively validated)
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

    # Check MultilineStr
    if _is_multiline_str(annotation):
        return errors

    # Check connection types
    if _is_connection_type(annotation):
        return errors

    # Check nested BaseModel
    try:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            # Recursively validate nested model
            return validate_input_schema(annotation)
    except TypeError:
        pass

    # If none of the above, it's not allowed
    type_name = getattr(annotation, "__name__", str(annotation))
    errors.append(
        f"Field '{field_name}' has disallowed type '{type_name}'. "
        f"Allowed: str, int, float, bool, MultilineStr, "
        f"BaseConnection subclasses, or nested BaseModel"
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
