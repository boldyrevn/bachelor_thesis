"""NodeRun model for tracking individual node executions."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .pipeline_run import RunStatus


class NodeRun(Base):
    """Represents a single node execution within a pipeline run.

    Tracks the status, timing, and output values for a node.
    Output values are stored as JSONB for flexible artifact tracking.
    Detailed logs are stored in log files on disk.
    """

    __tablename__ = "node_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    pipeline_run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        String(50), default=RunStatus.PENDING, nullable=False, index=True
    )
    output_values: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship to pipeline run
    pipeline_run: Mapped["PipelineRun"] = relationship(
        "PipelineRun",
        back_populates="node_runs",
    )

    def __repr__(self) -> str:
        return f"<NodeRun(id={self.id}, node_id={self.node_id}, status={self.status})>"


# Pydantic schemas for API validation


class NodeRunBase(BaseModel):
    """Base schema for node run data."""

    node_id: str
    node_type: str


class NodeRunCreate(NodeRunBase):
    """Schema for creating a new node run."""

    pass


class NodeRunUpdate(BaseModel):
    """Schema for updating a node run."""

    status: Optional[RunStatus] = None
    output_values: Optional[dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class NodeRunResponse(NodeRunBase):
    """Schema for node run response."""

    id: str
    pipeline_run_id: str
    status: RunStatus
    output_values: dict[str, Any]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True
