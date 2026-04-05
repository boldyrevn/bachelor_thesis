"""Node base class with typed input/output schemas for FlowForge pipeline execution."""

import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel


# Type variables for generic node execution
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseNode(ABC, Generic[InputT, OutputT]):
    """Abstract base class for all FlowForge nodes with typed schemas.

    Node responsibilities:
    1. Declare typed input_schema and output_schema as Pydantic models
    2. Implement execute(input: InputSchema, logger) -> OutputSchema
    3. Register with NodeRegistry via @NodeRegistry.register decorator

    Nodes are STATELESS - they only:
    - Execute code with validated inputs
    - Log progress via provided logger
    - Return typed outputs

    Scheduler responsibilities (NOT node's job):
    - Input validation
    - Context assembly
    - Template resolution
    - Upstream output collection

    Example:
        class TextInput(BaseModel):
            message: str = Field(description="Text to output")

        class TextOutput(BaseModel):
            text: str = Field(description="Output text")

        @NodeRegistry.register
        class TextOutputNode(BaseNode[TextInput, TextOutput]):
            node_type = "text_output"
            title = "Text Output"
            description = "Outputs a text message"
            category = "output"
            input_schema = TextInput
            output_schema = TextOutput

            def execute(self, inputs: TextInput, logger: logging.Logger) -> TextOutput:
                logger.info(f"Processing message: {inputs.message}")
                return TextOutput(text=inputs.message)
    """

    # Node metadata (must be overridden in subclasses)
    node_type: str = "base"
    title: str = "Base Node"
    description: str = "Base node class"
    category: str = "general"  # Grouping for UI: data, ml, transform, output, etc.

    # Typed schemas (must be overridden in subclasses)
    input_schema: type[InputT] | None = None
    output_schema: type[OutputT] | None = None

    @abstractmethod
    def execute(self, inputs: InputT, logger: logging.Logger) -> OutputT:
        """Execute the node logic with validated inputs.

        Args:
            inputs: Validated input parameters (Pydantic model instance)
            logger: Logger for streaming execution logs

        Returns:
            Typed output object (Pydantic model instance)

        Raises:
            Exception: For any execution failures
        """
        pass

    def get_input_schema_json(self) -> dict:
        """Get JSON Schema for input parameters.

        Returns:
            JSON Schema dict for frontend form generation
        """
        if self.input_schema is None:
            return {}
        return self.input_schema.model_json_schema()

    def get_output_schema_json(self) -> dict:
        """Get JSON Schema for output artifacts.

        Returns:
            JSON Schema dict for frontend output handle generation
        """
        if self.output_schema is None:
            return {}
        return self.output_schema.model_json_schema()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(type={self.node_type}, category={self.category})>"
