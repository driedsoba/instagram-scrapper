"""
This module defines the data models for artifact metadata and content using Pydantic.
"""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ArtifactMetadata(BaseModel):
    id: str
    case_id: str
    description: str
    identifier: str
    platform: str = "instagram"
    display_name: str | None = None
    profile_pic: str | None = None
    created_datetime: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: str = "processing"


class MediaContent(BaseModel):
    media_type: str  # "image" or "video"
    original_url: str
    original_thumbnail_url: str | None = None  # videos only
    url: str | None = None           # set after blob download
    thumbnail_url: str | None = None  # set after blob download


class ArtifactContent(BaseModel):
    artifact_id: str
    error_message: str = ""
    owners: list[str] = []
    caption: str | None = None
    datetime: str | None = None
    content_type: str  # "post" or "reel"
    media_content: list[MediaContent] = []


class BlobRecord(BaseModel):
    blob_id: str
    file_path: str
    content_type: str
