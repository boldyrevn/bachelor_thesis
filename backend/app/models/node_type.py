"""NodeType model for persisting node type metadata in the database."""

import uuid
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class NodeType(Base, TimestampMixin):
    """Defines metadata for a node type.

    This table stores information about all available node types, including
    their human-readable names, descriptions, categories, and JSON schemas
    for input/output validation. Used by the frontend to dynamically render
    node configuration forms without hardcoding node types.

    Populated automatically by the NodeScanner on application startup.
    """

    __tablename__ = "node_types"

    node_type: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        nullable=False,
        comment="Unique node type identifier (e.g., 'text_output', 'spark_transform')",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable node name for UI display",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed description of what the node does",
    )
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Category for grouping in UI (e.g., 'data', 'ml', 'transform', 'output')",
    )
    input_schema: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="JSON Schema for node input parameters (frontend form generation)",
    )
    output_schema: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="JSON Schema for node output artifacts (output handle generation)",
    )
    version: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        comment="Schema version for migration tracking",
    )
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment="Whether this node type is available for use",
    )

    def __repr__(self) -> str:
        return (
            f"<NodeType(node_type={self.node_type}, title={self.title}, "
            f"category={self.category}, is_active={self.is_active})>"
        )


# Pydantic schemas for API validation


class NodeTypeBase(BaseModel):
    """Base schema for node type data."""

    node_type: str = Field(description="Unique node type identifier")
    title: str = Field(description="Human-readable node name")
    description: str = Field(description="Detailed description")
    category: str = Field(description="Category for UI grouping")
    input_schema: dict = Field(description="JSON Schema for input parameters")
    output_schema: dict = Field(description="JSON Schema for output artifacts")
    version: int = Field(description="Schema version")
    is_active: bool = Field(description="Whether node type is available")


class NodeTypeResponse(NodeTypeBase):
    """Schema for node type API response."""

    class Config:
        from_attributes = True


class NodeTypeListResponse(BaseModel):
    """Schema for listing node types."""

    node_types: list[NodeTypeResponse]
    total: int = Field(description="Total number of node types")
