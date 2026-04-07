"""
This module defines the data models for artifact metadata and content using Pydantic.
"""
from datetime import UTC, datetime

from pydantic import BaseModel, Field

class ArtifactMetadata(BaseModel):
    id: str
    case_id: str
    description: str
    identifier: str
    created_datetime: str = Field(default_factory = lambda: datetime.now(UTC).isoformat())
    status: str = "processing"


class ArtifactContent(BaseModel):
    pass
