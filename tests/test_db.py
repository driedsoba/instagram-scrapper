"""Tests for database/db.py -- MongoDB operations using mongomock."""

from unittest.mock import patch

import mongomock
import pytest

import database.db as db


@pytest.fixture(autouse=True)
def mock_mongodb():
    """Replace MongoDB with mongomock for all tests."""
    client = mongomock.MongoClient()
    mock_db = client["instagram_scrapper"]
    with patch("database.db.init_db", return_value=mock_db):
        yield mock_db


class TestCreateArtifactMetadata:
    def test_inserts_with_correct_fields(self, mock_mongodb):
        db.create_artifact_metadata("a1", "c1", "user1", "test desc")
        doc = mock_mongodb["artifacts"].find_one({"_id": "a1"})
        assert doc is not None
        assert doc["case_id"] == "c1"
        assert doc["identifier"] == "user1"
        assert doc["status"] == "processing"
        assert doc["platform"] == "instagram"


class TestUpdateMetadataStatus:
    def test_updates_status(self, mock_mongodb):
        db.create_artifact_metadata("a1", "c1", "user1", "desc")
        db.update_metadata_status("a1", "c1", "downloading")
        doc = mock_mongodb["artifacts"].find_one({"_id": "a1"})
        assert doc["status"] == "downloading"


class TestUpdateResults:
    def test_inserts_content_items(self, mock_mongodb):
        items = [
            {"content_type": "post", "caption": "Hello", "media_content": []},
            {"content_type": "reel", "caption": "World", "media_content": []},
        ]
        db.update_results("a1", items)
        docs = list(mock_mongodb["contents"].find({"artifact_id": "a1"}))
        assert len(docs) == 2


class TestGetArtifact:
    def test_returns_artifact_with_contents(self, mock_mongodb):
        db.create_artifact_metadata("a1", "c1", "user1", "desc")
        db.update_results(
            "a1", [{"content_type": "post", "caption": "Hi", "media_content": []}]
        )
        result = db.get_artifact("a1")
        assert result is not None
        assert result["artifact_id"] == "a1"
        assert len(result["contents"]) == 1

    def test_returns_none_for_missing(self):
        assert db.get_artifact("nonexistent") is None


class TestGetAllArtifacts:
    def test_returns_all(self):
        db.create_artifact_metadata("a1", "c1", "user1", "desc1")
        db.create_artifact_metadata("a2", "c2", "user2", "desc2")
        assert len(db.get_all_artifacts()) == 2


class TestFindActiveArtifact:
    def test_finds_processing(self):
        db.create_artifact_metadata("a1", "c1", "user1", "desc")
        assert db.find_active_artifact_by_identifier("user1") is not None

    def test_returns_none_for_completed(self):
        db.create_artifact_metadata("a1", "c1", "user1", "desc")
        db.update_metadata_status("a1", "c1", "success")
        assert db.find_active_artifact_by_identifier("user1") is None


class TestPaginationCursor:
    def test_upsert_and_get(self):
        db.upsert_pagination_cursor("a1", "post", "cursor123", True)
        cursor = db.get_pagination_cursor("a1", "post")
        assert cursor is not None
        assert cursor["next_cursor"] == "cursor123"
        assert cursor["has_more"] is True


class TestBlobOperations:
    def test_create_and_get(self):
        db.create_blob("b1", "/path/to/file.jpg", "image/jpeg")
        blob = db.get_blob("b1")
        assert blob is not None
        assert blob["blob_id"] == "b1"
        assert blob["content_type"] == "image/jpeg"

    def test_get_returns_none_for_missing(self):
        assert db.get_blob("nonexistent") is None


class TestClaimOrGetActiveArtifact:
    def test_creates_new(self):
        aid, created = db.claim_or_get_active_artifact("a1", "c1", "user1", "desc")
        assert aid == "a1"
        assert created is True

    def test_returns_existing_active(self):
        db.create_artifact_metadata("a1", "c1", "user1", "desc")
        aid, created = db.claim_or_get_active_artifact("a2", "c2", "user1", "desc2")
        assert aid == "a1"
        assert created is False
