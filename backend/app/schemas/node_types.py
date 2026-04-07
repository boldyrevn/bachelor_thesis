"""Custom Pydantic types for FlowForge node input schemas.

These types are used in node input_schema classes to declare
what kind of inputs a node accepts. Each type maps to a specific
frontend form widget and backend validation rule.
"""

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


DateStr = Annotated[str, Field(json_schema_extra={"format": "date"})]
"""A string representing an ISO date (YYYY-MM-DD).

Renders as a date picker in the frontend. The value is stored as
a string — the node is responsible for parsing it.

Usage:
    class MyNodeInput(BaseModel):
        start_date: DateStr = Field(description="Start date (YYYY-MM-DD)")

JSON Schema output:
    "start_date": {"type": "string", "format": "date", "description": "..."}
"""


DateTimeStr = Annotated[str, Field(json_schema_extra={"format": "date-time"})]
"""A string representing an ISO datetime (YYYY-MM-DDTHH:MM:SS).

Assumes UTC timezone if none is specified. Renders as a datetime picker
in the frontend.

Usage:
    class MyNodeInput(BaseModel):
        timestamp: DateTimeStr = Field(description="Event timestamp (UTC)")

JSON Schema output:
    "timestamp": {"type": "string", "format": "date-time", "description": "..."}
"""
