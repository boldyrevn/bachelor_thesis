"""Custom Pydantic types for FlowForge node input schemas."""

from typing import Annotated

from pydantic import Field


MultilineStr = Annotated[str, Field(json_schema_extra={"format": "multiline"})]
"""A string type that renders as a <textarea> in the frontend form.

Usage:
    class MyNodeInput(BaseModel):
        query: MultilineStr = Field(description="SQL query to execute")

JSON Schema output:
    "query": {"type": "string", "format": "multiline", "description": "..."}
"""
