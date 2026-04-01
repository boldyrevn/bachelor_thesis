"""Pipeline model for storing DAG definitions."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Pipeline(Base, TimestampMixin):
    """Represents a pipeline definition with its graph structure.

    Contains the DAG definition including nodes, edges, and configuration.
    The graph_definition stores the React Flow state as JSON.
    """

    __tablename__ = "pipelines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    graph_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    def __repr__(self) -> str:
        return f"<Pipeline(id={self.id}, name={self.name})>"


# Pydantic schemas for API validation


class NodeSpec(BaseModel):
    """Specification for a single node in the pipeline."""

    id: str
    type: str
    position: dict[str, float]
    data: dict[str, Any]


class EdgeSpec(BaseModel):
    """Specification for an edge between nodes."""

    id: str
    source: str
    target: str
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None


class PipelineGraph(BaseModel):
    """Graph definition for a pipeline."""

    nodes: list[NodeSpec] = Field(default_factory=list)
    edges: list[EdgeSpec] = Field(default_factory=list)


class PipelineBase(BaseModel):
    """Base schema for pipeline data."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class PipelineCreate(PipelineBase):
    """Schema for creating a new pipeline."""

    graph_definition: dict[str, Any] = Field(default_factory=dict)


class PipelineUpdate(BaseModel):
    """Schema for updating a pipeline."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    graph_definition: Optional[dict[str, Any]] = None


class PipelineResponse(PipelineBase):
    """Schema for pipeline response."""

    id: str
    graph_definition: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
