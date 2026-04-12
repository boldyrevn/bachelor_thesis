"""Sexual compatibility check node."""

import logging

from pydantic import BaseModel, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry


class CompatibilityInput(BaseModel):
    """Input parameters for compatibility check."""

    member_length_cm: float = Field(
        gt=0,
        description="Length of the member (cm)",
    )
    vaginal_depth_cm: float = Field(
        gt=0,
        description="Vaginal depth (cm)",
    )


class CompatibilityOutput(BaseModel):
    """Output of the compatibility check."""

    fits: bool = Field(description="Whether the member fits")
    message: str = Field(description="Human-readable result")
    clearance_cm: float = Field(description="Remaining space in cm (can be negative)")


@NodeRegistry.register
class CompatibilityNode(BaseNode[CompatibilityInput, CompatibilityOutput]):
    """Checks if a member fits into a vagina based on dimensions."""

    node_type = "compatibility_check"
    title = "Compatibility Check"
    description = "Checks whether a member fits based on length and depth parameters"
    category = "utility"
    input_schema = CompatibilityInput
    output_schema = CompatibilityOutput

    def execute(
        self, inputs: CompatibilityInput, logger: logging.Logger
    ) -> CompatibilityOutput:
        clearance = inputs.vaginal_depth_cm - inputs.member_length_cm
        fits = clearance >= 0

        if fits:
            message = f"✅ Поместится. Запас: {clearance:.1f} см"
        else:
            message = f"❌ Не поместится. Не хватает: {abs(clearance):.1f} см"

        logger.info(
            f"member_length={inputs.member_length_cm}cm, "
            f"vaginal_depth={inputs.vaginal_depth_cm}cm → fits={fits}"
        )

        return CompatibilityOutput(
            fits=fits,
            message=message,
            clearance_cm=round(clearance, 2),
        )
