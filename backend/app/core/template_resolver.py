"""Jinja2 template resolver for pipeline parameter resolution.

This module provides Jinja2-based template resolution for node inputs,
pipeline parameters, and upstream outputs.

Supported syntax:
- {{ params.name }} - Pipeline parameters
- {{ node_id.output_name }} - Upstream node outputs
- {{ params.date | upper }} - Jinja2 filters
- {% if params.env == 'prod' %}...{% endif %} - Jinja2 control structures
"""

from typing import Any

from jinja2 import BaseLoader, Environment, TemplateError, Undefined


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

    Examples:
        >>> resolve_template("Hello {{ params.name }}!", params={"name": "World"})
        'Hello World!'

        >>> resolve_template("Result: {{ node1.text | upper }}",
        ...                 upstream_outputs={"node1": {"text": "hello"}})
        'Result: HELLO'

        >>> resolve_template("{% if params.env == 'prod' %}Production{% else %}Dev{% endif %}",
        ...                 params={"env": "prod"})
        'Production'
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
    # {{ node1.text }} instead of {{ upstream_outputs.node1.text }}
    for node_id, outputs in upstream_outputs.items():
        context[node_id] = outputs

    try:
        tpl = jinja_env.from_string(template)
        return tpl.render(**context)
    except TemplateError as e:
        # Return original template with error message
        return f"TEMPLATE_ERROR: {str(e)}"


def resolve_dict_values(
    data: dict[str, Any],
    params: dict[str, Any] | None = None,
    upstream_outputs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve all string values in a dictionary using Jinja2 templates.

    Recursively processes nested dictionaries and lists.

    Args:
        data: Dictionary with potentially templated string values
        params: Pipeline parameters
        upstream_outputs: Upstream node outputs

    Returns:
        Dictionary with all templates resolved
    """
    if params is None:
        params = {}
    if upstream_outputs is None:
        upstream_outputs = {}

    resolved = {}
    for key, value in data.items():
        resolved[key] = _resolve_value(value, params, upstream_outputs)

    return resolved


def _resolve_value(
    value: Any,
    params: dict[str, Any],
    upstream_outputs: dict[str, dict[str, Any]],
) -> Any:
    """Recursively resolve templates in a value."""
    if isinstance(value, str):
        return resolve_template(value, params, upstream_outputs)
    elif isinstance(value, dict):
        return resolve_dict_values(value, params, upstream_outputs)
    elif isinstance(value, list):
        return [_resolve_value(item, params, upstream_outputs) for item in value]
    else:
        return value
