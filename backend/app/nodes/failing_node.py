"""Failing node — always raises an exception for testing error handling."""

import logging

from pydantic import BaseModel, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry


class FailingNodeInput(BaseModel):
    """Input parameters for FailingNode."""

    error_message: str = Field(
        default="This node is supposed to fail.",
        description="Custom error message to raise",
    )


class FailingNodeOutput(BaseModel):
    """Output — never returned since the node always fails."""

    dummy: str = Field(description="Placeholder, never used")


@NodeRegistry.register
class FailingNode(BaseNode[FailingNodeInput, FailingNodeOutput]):
    """Always raises RuntimeError. Used to test error handling and log capture."""

    node_type = "failing_node"
    title = "Failing Node"
    description = (
        "Always raises an exception — for testing error handling and log capture"
    )
    category = "testing"
    input_schema = FailingNodeInput
    output_schema = FailingNodeOutput

    def execute(
        self, inputs: FailingNodeInput, logger: logging.Logger
    ) -> FailingNodeOutput:
        logger.info("FailingNode started — about to raise an exception")
        print("This is stdout output before the crash")

        raise RuntimeError(inputs.error_message)
