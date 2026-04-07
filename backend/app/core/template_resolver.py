"""Jinja2 template resolver for pipeline parameter resolution.

This module provides Jinja2-based template resolution for node inputs,
pipeline parameters, and upstream outputs, followed by type casting
based on Pydantic input schema annotations.

Supported syntax:
- {{ params.name }} - Pipeline parameters
- {{ node_id.output_name }} - Upstream node outputs
- {{ params.date | upper }} - Jinja2 filters
- {% if params.env == 'prod' %}...{% endif %} - Jinja2 control structures
"""

import logging
from typing import Any

from jinja2 import BaseLoader, Environment, TemplateError, Undefined
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Create Jinja2 environment
jinja_env = Environment(
    loader=BaseLoader(),
    autoescape=False,  # Safe for non-HTML contexts
    undefined=Undefined,  # Return empty string for missing vars
)


def resolve_template(
    template: str,
    params: dict[str, Any] | None = None,
    upstream_outputs: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Resolve a Jinja2 template string with pipeline params and upstream outputs.

    Args:
        template: Template string potentially containing Jinja2 syntax
        params: Pipeline parameters (accessible as {{ params.key }})
        upstream_outputs: Upstream node outputs (accessible as {{ node_id.output_name }})

    Returns:
        Resolved string with all template references replaced
    """
    if params is None:
        params = {}
    if upstream_outputs is None:
        upstream_outputs = {}

    # Check if template actually has Jinja2 syntax
    if "{{" not in template and "{%" not in template:
        return template

    # Build context for template rendering
    context = {
        "params": params,
    }

    # Add upstream outputs at top level for easy access
    for node_id, outputs in upstream_outputs.items():
        context[node_id] = outputs

    try:
        tpl = jinja_env.from_string(template)
        return tpl.render(**context)
    except TemplateError as e:
        logger.warning(f"Template resolution failed: {e}")
        return f"TEMPLATE_ERROR: {str(e)}"


def resolve_dict_values(
    data: dict[str, Any],
    input_schema: type[BaseModel] | None = None,
    params: dict[str, Any] | None = None,
    upstream_outputs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve string values in a dictionary using Jinja2, then cast to schema types.

    Two-step process:
    1. Jinja2 template resolution for all string values
    2. Type casting based on input_schema field annotations (e.g. str → int)

    Args:
        data: Dictionary with potentially templated string values
        input_schema: Pydantic model class for type casting. If None,
            only Jinja2 resolution is performed.
        params: Pipeline parameters
        upstream_outputs: Upstream node outputs

    Returns:
        Dictionary with templates resolved and values cast to target types
    """
    if params is None:
        params = {}
    if upstream_outputs is None:
        upstream_outputs = {}

    # Step 1: Jinja2 template resolution
    resolved = {}
    for key, value in data.items():
        resolved[key] = _resolve_templates(value, params, upstream_outputs)

    # Step 2: Type casting based on input_schema
    if input_schema is not None:
        resolved = _cast_to_schema(resolved, input_schema)

    return resolved


def _resolve_templates(
    value: Any,
    params: dict[str, Any],
    upstream_outputs: dict[str, dict[str, Any]],
) -> Any:
    """Recursively resolve Jinja2 templates in a value."""
    if isinstance(value, str):
        # Only call Jinja2 if template syntax is present
        if "{{" in value or "{%" in value:
            return resolve_template(value, params, upstream_outputs)
        return value
    elif isinstance(value, dict):
        return resolve_dict_values(
            value, params=params, upstream_outputs=upstream_outputs
        )
    elif isinstance(value, list):
        return [_resolve_templates(item, params, upstream_outputs) for item in value]
    else:
        return value


def _cast_to_schema(data: dict[str, Any], schema: type[BaseModel]) -> dict[str, Any]:
    """Cast resolved values to types declared in Pydantic input_schema.

    For each field in the schema, attempts to convert the resolved value
    to the field's annotated type.

    Args:
        data: Dictionary with resolved string values
        schema: Pydantic model class with type annotations

    Returns:
        Dictionary with values cast to their target types
    """
    casted = {}
    for field_name, field_info in schema.model_fields.items():
        if field_name not in data:
            continue

        value = data[field_name]
        target_type = field_info.annotation

        casted[field_name] = _cast_value(value, target_type)

    # Keep any extra keys not in schema (e.g. unknown fields passed by frontend)
    for key in data:
        if key not in casted:
            casted[key] = data[key]

    return casted


def _cast_value(value: Any, target_type: type) -> Any:
    """Cast a single value to the target type.

    Handles: int, float, bool, str, and common container types.
    For non-primitive types (e.g. Pydantic models, BaseConnection), returns value as-is.

    Args:
        value: Value to cast (usually a string from template resolution)
        target_type: Target Python type

    Returns:
        Value cast to target type, or original value if cast not possible
    """
    # Already the right type or None
    if value is None:
        return None

    if isinstance(value, target_type):
        return value

    # bool: "true"/"True"/"1" → True, "false"/"False"/"0" → False
    if target_type is bool:
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)

    # int: "42" → 42
    if target_type is int:
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                logger.warning(f"Cannot cast '{value}' to int, keeping as-is")
                return value
        return int(value)

    # float: "3.14" → 3.14
    if target_type is float:
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                logger.warning(f"Cannot cast '{value}' to float, keeping as-is")
                return value
        return float(value)

    # str: just return as-is (already resolved)
    if target_type is str:
        return value

    # For complex types (BaseConnection, custom models, etc.) — return as-is
    # The connection resolver handles these separately
    return value
