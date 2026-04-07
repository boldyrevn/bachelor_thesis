"""PipelineRun model for tracking pipeline executions."""

import enum
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class RunStatus(str, enum.Enum):
    """Status of a pipeline or node run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineRun(Base):
    """Represents a single execution of a pipeline.

    Tracks the overall status, parameters, and timing of a pipeline run.
    Contains references to all NodeRun instances for this execution.
    The version_id points to the exact PipelineVersion that was executed.
    """

    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
        comment="The exact PipelineVersion that was executed",
    )
    status: Mapped[RunStatus] = mapped_column(
        String(50), default=RunStatus.PENDING, nullable=False, index=True
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship to node runs
    node_runs: Mapped[list["NodeRun"]] = relationship(
        "NodeRun",
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )

    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate run duration if completed."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def __repr__(self) -> str:
        return f"<PipelineRun(id={self.id}, version_id={self.version_id}, status={self.status})>"


# Pydantic schemas for API validation


class PipelineRunBase(BaseModel):
    """Base schema for pipeline run data."""

    version_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class PipelineRunCreate(PipelineRunBase):
    """Schema for creating a new pipeline run."""

    pass


class PipelineRunResponse(PipelineRunBase):
    """Schema for pipeline run response."""

    id: str
    status: RunStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj: PipelineRun) -> "PipelineRunResponse":
        """Create response from ORM object with computed duration."""
        duration = obj.duration
        return cls(
            id=obj.id,
            version_id=obj.version_id,
            status=obj.status,
            parameters=obj.parameters,
            started_at=obj.started_at,
            completed_at=obj.completed_at,
            error_message=obj.error_message,
            duration_seconds=duration.total_seconds() if duration else None,
        )
