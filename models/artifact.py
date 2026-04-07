"""
This module defines the data models for artifact metadata and content using Pydantic.
"""
from datetime import UTC, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ArtifactMetadata(BaseModel):
    id: str
    case_id: str
    description: str
    identifier: str
    platform: str = "instagram"
    display_name: Optional[str] = None
    profile_pic: Optional[str] = None
    created_datetime: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: str = "processing"


class MediaContent(BaseModel):
    media_type: str  # "image" or "video"
    original_url: str
    original_thumbnail_url: Optional[str] = None  # videos only
    url: Optional[str] = None           # set after blob download
    thumbnail_url: Optional[str] = None  # set after blob download


class ArtifactContent(BaseModel):
    artifact_id: str
    error_message: str = ""
    owners: List[str] = []
    caption: Optional[str] = None
    datetime: Optional[str] = None
    content_type: str  # "post" or "reel"
    media_content: List[MediaContent] = []


class BlobRecord(BaseModel):
    blob_id: str
    file_path: str
    content_type: str
