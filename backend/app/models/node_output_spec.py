"""NodeOutputSpec model for defining typed output specifications."""

import enum
import uuid
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OutputType(str, enum.Enum):
    """Supported artifact output types."""

    S3_PATH = "s3_path"
    DB_TABLE = "db_table"
    STRING = "string"
    NUMBER = "number"
    MODEL_ARTIFACT = "model_artifact"


class NodeOutputSpec(Base):
    """Defines the output specification for a node type.

    Maps node types to their expected output artifacts.
    Used for validation and dependency resolution.
    """

    __tablename__ = "node_output_specs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    node_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    output_name: Mapped[str] = mapped_column(String(255), nullable=False)
    output_type: Mapped[OutputType] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<NodeOutputSpec(node_type={self.node_type}, "
            f"output_name={self.output_name}, type={self.output_type})>"
        )


# Pydantic schemas for API validation


class NodeOutputSpecBase(BaseModel):
    """Base schema for node output spec data."""

    node_type: str
    output_name: str
    output_type: OutputType
    description: Optional[str] = None


class NodeOutputSpecCreate(NodeOutputSpecBase):
    """Schema for creating a node output spec."""

    pass


class NodeOutputSpecResponse(NodeOutputSpecBase):
    """Schema for node output spec response."""

    id: str

    class Config:
        from_attributes = True


class NodeInstanceOutput(BaseModel):
    """Represents a resolved output value for a specific node instance."""

    node_id: str
    output_name: str
    output_type: OutputType
    value: str | int | float | dict


class ResolvedContext(BaseModel):
    """Resolved context for pipeline execution.

    Contains all resolved artifact references for a node execution.
    """

    pipeline_params: dict[str, str] = Field(default_factory=dict)
    node_outputs: dict[str, NodeInstanceOutput] = Field(default_factory=dict)

    def resolve_template(self, template: str) -> str:
        """Resolve {{ node_id.output_name }} templates.

        Args:
            template: String potentially containing {{ ... }} references

        Returns:
            String with all references resolved to actual values
        """
        import re

        def replace_ref(match: re.Match) -> str:
            ref = match.group(1)  # e.g., "node1.s3_path"
            parts = ref.split(".", 1)
            if len(parts) != 2:
                return match.group(0)  # Invalid format, keep as-is

            node_id, output_name = parts
            key = f"{node_id}.{output_name}"

            if key in self.node_outputs:
                return str(self.node_outputs[key].value)
            return match.group(0)  # Not found, keep as-is

        return re.sub(r"\{\{\s*(.+?)\s*\}\}", replace_ref, template)
