"""Text output node - Simple implementation with typed schemas."""

import logging

from pydantic import BaseModel, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry


class TextOutputInput(BaseModel):
    """Input parameters for TextOutputNode."""

    message: str = Field(
        default="Hello, World!",
        description="Text message to output",
    )


class TextOutputOutput(BaseModel):
    """Output artifacts for TextOutputNode."""

    text: str = Field(description="The output message")


@NodeRegistry.register
class TextOutputNode(BaseNode[TextOutputInput, TextOutputOutput]):
    """Simple text output node for testing.

    Outputs a text message.

    Configuration:
        message: The text message to output

    Outputs:
        text: The output message string
    """

    node_type = "text_output"
    title = "Text Output"
    description = "Outputs a text message"
    category = "output"

    input_schema = TextOutputInput
    output_schema = TextOutputOutput

    def execute(
        self, inputs: TextOutputInput, logger: logging.Logger
    ) -> TextOutputOutput:
        """Execute the text output node.

        Args:
            inputs: Validated input parameters
            logger: Logger for streaming execution logs

        Returns:
            TextOutputOutput with the text result
        """
        logger.info(f"Starting text output node with message: {inputs.message}")
        logger.info(f"Text output node completed successfully")

        return TextOutputOutput(text=inputs.message)
