"""Dummy node with a very long name to test UI rendering."""

import logging

from pydantic import BaseModel, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry


class AdvancedDataTransformationPipelineInput(BaseModel):
    source_value: str = Field(description="Input value to transform")


class AdvancedDataTransformationPipelineOutput(BaseModel):
    result: str = Field(description="Transformed result")


@NodeRegistry.register
class AdvancedDataTransformationPipelineNode(
    BaseNode[
        AdvancedDataTransformationPipelineInput,
        AdvancedDataTransformationPipelineOutput,
    ]
):
    """A dummy node with a very long name to test how the UI handles long titles."""

    node_type = "advanced_data_transformation_pipeline"
    title = "Advanced Data Transformation Pipeline Configuration Node"
    description = "This is a dummy node with an extremely long name and description to test how the user interface handles rendering of lengthy text in the node selection dialog"
    category = "transform"
    input_schema = AdvancedDataTransformationPipelineInput
    output_schema = AdvancedDataTransformationPipelineOutput

    def execute(
        self, inputs: AdvancedDataTransformationPipelineInput, logger: logging.Logger
    ) -> AdvancedDataTransformationPipelineOutput:
        logger.info(f"Transforming: {inputs.source_value}")
        return AdvancedDataTransformationPipelineOutput(
            result=f"Transformed: {inputs.source_value}"
        )
