"""PipelineVersion model for storing pipeline definitions with version tracking."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class PipelineVersion(Base, TimestampMixin):
    """Represents a versioned pipeline definition.

    Each save creates a new row with an incremented version number.
    Only one version per pipeline has is_current=True at any time.
    Pipeline runs reference the version_id that was executed.
    """

    __tablename__ = "pipeline_versions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    pipeline_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
        comment="Logical pipeline identifier (groups versions together)",
    )
    version: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
        comment="Sequential version number within a pipeline",
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, comment="Pipeline name"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Pipeline description"
    )
    graph_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, comment="React Flow graph state"
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="True if this is the latest version of the pipeline",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<PipelineVersion(id={self.id}, pipeline_id={self.pipeline_id}, "
            f"version={self.version}, name={self.name})>"
        )


# Pydantic schemas for API validation


class PipelineVersionBase(BaseModel):
    """Base schema for pipeline version data."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    graph_definition: dict[str, Any] = Field(default_factory=dict)


class PipelineVersionCreate(PipelineVersionBase):
    """Schema for creating a new pipeline version."""

    pass


class PipelineVersionUpdate(BaseModel):
    """Schema for updating pipeline data (creates new version)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    graph_definition: Optional[dict[str, Any]] = None


class PipelineVersionResponse(BaseModel):
    """Schema for pipeline version response."""

    id: str
    pipeline_id: str
    version: int
    name: str
    description: Optional[str]
    graph_definition: dict[str, Any]
    is_current: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PipelineListItem(BaseModel):
    """Summary item for pipeline list (shows latest version info)."""

    pipeline_id: str
    name: str
    description: Optional[str] = None
    latest_version: int
    is_current_id: str
    node_count: int = Field(default=0)
    edge_count: int = Field(default=0)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
