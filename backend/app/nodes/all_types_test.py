"""All Types Test Node - Demonstrates all supported field types.

This node is used for testing frontend form rendering of all parameter types:
- Primitives: str, int, float, bool
- Custom strings: multiline, date, datetime
- Collections: dict[str, int], list[str]
- Union types: Union[str, int], Union[bool, str, int]
- Optional types: Optional[str], Optional[int]
"""

import logging
from datetime import date, datetime
from typing import Optional, Union

from pydantic import BaseModel, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry


class AllTypesTestInput(BaseModel):
    """Input parameters demonstrating all supported field types."""

    # ─── Required fields (only these 2 are required) ────────────────────────

    required_string: str = Field(
        description="A simple required string parameter",
    )

    required_int: int = Field(
        description="A required integer parameter",
    )

    # ─── Optional primitives ────────────────────────────────────────────────

    optional_str: Optional[str] = Field(
        default=None,
        description="An optional string — can be left empty",
    )

    optional_int: Optional[int] = Field(
        default=None,
        description="An optional integer",
    )

    optional_float: Optional[float] = Field(
        default=None,
        description="An optional float number",
    )

    optional_bool: Optional[bool] = Field(
        default=None,
        description="An optional boolean toggle",
    )

    # ─── Primitives with defaults ───────────────────────────────────────────

    string_with_default: str = Field(
        default="default value",
        description="String with a default value",
    )

    int_with_default: int = Field(
        default=42,
        description="Integer with a default value",
    )

    float_with_default: float = Field(
        default=3.14,
        description="Float with a default value (pi)",
    )

    bool_with_default: bool = Field(
        default=False,
        description="Boolean flag with default False",
    )

    # ─── Custom string formats ──────────────────────────────────────────────

    multiline_text: str = Field(
        default="Enter\nmultiple\nlines\nhere",
        description="A multiline text area for longer content",
        json_schema_extra={"format": "multiline"},
    )

    date_field: str = Field(
        # default="2025-01-01",
        description="A date value (YYYY-MM-DD format)",
        json_schema_extra={"format": "date"},
    )

    datetime_field: str = Field(
        # default="2025-01-01T12:00:00",
        description="A datetime value in ISO format",
        json_schema_extra={"format": "date-time"},
    )

    # ─── Dict type ──────────────────────────────────────────────────────────

    string_to_int_dict: dict[str, int] = Field(
        default_factory=dict,
        description="A dictionary mapping strings to integers (e.g. {'a': 1, 'b': 2})",
    )

    string_to_float_dict: dict[str, float] = Field(
        default_factory=dict,
        description="A dictionary mapping strings to floats (e.g. {'price': 9.99})",
    )

    # ─── List type ──────────────────────────────────────────────────────────

    list_of_strings: list[str] = Field(
        default_factory=list,
        description="A list of string values",
    )

    list_of_ints: list[int] = Field(
        default_factory=list,
        description="A list of integer values",
    )

    list_of_floats: list[float] = Field(
        default_factory=list,
        description="A list of float values",
    )

    # ─── Union types ────────────────────────────────────────────────────────

    str_or_int: Union[str, int] = Field(
        default="default",
        description="A value that can be either a string or an integer",
    )

    complex_union: Union[str, int, float, bool] = Field(
        default="hello",
        description="A value that can be str, int, float, or bool",
    )

    optional_union: Optional[Union[str, int]] = Field(
        default=None,
        description="Optional union — can be null, str, or int",
    )


class AllTypesTestOutput(BaseModel):
    """Output artifacts — simple echo of all input values."""

    summary: str = Field(description="Summary of all received input values")
    total_params: int = Field(description="Total number of non-null parameters received")


@NodeRegistry.register
class AllTypesTestNode(BaseNode[AllTypesTestInput, AllTypesTestOutput]):
    """Test node with all supported field types for frontend verification.

    Use this node to verify that:
    - All primitive types render correctly
    - Date/datetime pickers work
    - Dict/list editors function
    - Union type selectors operate
    - Required/optional markers display properly
    """

    node_type = "all_types_test"
    title = "All Types Test"
    description = "Test node with every supported field type — used for frontend form verification"
    category = "testing"

    input_schema = AllTypesTestInput
    output_schema = AllTypesTestOutput

    def execute(
        self, inputs: AllTypesTestInput, logger: logging.Logger
    ) -> AllTypesTestOutput:
        """Execute the test node — echo all inputs as summary.

        Args:
            inputs: Validated input parameters
            logger: Logger for streaming execution logs

        Returns:
            AllTypesTestOutput with summary
        """
        logger.info(f"Starting AllTypesTestNode")
        logger.info(f"  required_string: {inputs.required_string}")
        logger.info(f"  required_int: {inputs.required_int}")
        logger.info(f"  optional_str: {inputs.optional_str}")
        logger.info(f"  optional_int: {inputs.optional_int}")
        logger.info(f"  optional_float: {inputs.optional_float}")
        logger.info(f"  optional_bool: {inputs.optional_bool}")
        logger.info(f"  string_with_default: {inputs.string_with_default}")
        logger.info(f"  int_with_default: {inputs.int_with_default}")
        logger.info(f"  float_with_default: {inputs.float_with_default}")
        logger.info(f"  bool_with_default: {inputs.bool_with_default}")
        logger.info(f"  multiline_text: {inputs.multiline_text}")
        logger.info(f"  date_field: {inputs.date_field}")
        logger.info(f"  datetime_field: {inputs.datetime_field}")
        logger.info(f"  string_to_int_dict: {inputs.string_to_int_dict}")
        logger.info(f"  string_to_float_dict: {inputs.string_to_float_dict}")
        logger.info(f"  list_of_strings: {inputs.list_of_strings}")
        logger.info(f"  list_of_ints: {inputs.list_of_ints}")
        logger.info(f"  list_of_floats: {inputs.list_of_floats}")
        logger.info(f"  str_or_int: {inputs.str_or_int}")
        logger.info(f"  complex_union: {inputs.complex_union}")
        logger.info(f"  optional_union: {inputs.optional_union}")

        # Count non-None params
        non_null_count = 0
        for key, value in inputs.model_dump().items():
            if value is not None and value != [] and value != {}:
                non_null_count += 1

        logger.info(f"Total non-null parameters: {non_null_count}")
        logger.info(f"AllTypesTestNode completed successfully")

        return AllTypesTestOutput(
            summary=f"Received {non_null_count} non-null parameters",
            total_params=non_null_count,
        )
