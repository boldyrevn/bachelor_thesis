"""MultiplyTwoNumbers node — multiplies two numbers."""

import logging

from pydantic import BaseModel, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry


class MultiplyTwoNumbersInput(BaseModel):
    a: int = Field(description="First number")
    b: int = Field(description="Second number")


class MultiplyTwoNumbersOutput(BaseModel):
    result: int = Field(description="Product of a and b")


@NodeRegistry.register
class MultiplyTwoNumbersNode(
    BaseNode[MultiplyTwoNumbersInput, MultiplyTwoNumbersOutput]
):
    """Multiplies two numbers together."""

    node_type = "multiply_two_numbers"
    title = "Multiply Two Numbers"
    description = "Multiplies two integer inputs and returns the product"
    category = "transform"
    input_schema = MultiplyTwoNumbersInput
    output_schema = MultiplyTwoNumbersOutput

    def execute(
        self, inputs: MultiplyTwoNumbersInput, logger: logging.Logger
    ) -> MultiplyTwoNumbersOutput:
        logger.info(f"Multiplying {inputs.a} × {inputs.b}")
        return MultiplyTwoNumbersOutput(result=inputs.a * inputs.b)
