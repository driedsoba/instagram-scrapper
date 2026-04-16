"""Tests for function_app.py -- input validation and response formatting."""

from unittest.mock import MagicMock, patch

from function_app import (
    _build_contents,
    _build_metadata,
    _format_artifact,
    validate_input,
)


def _make_request(body):
    req = MagicMock()
    req.get_json.return_value = body
    return req


class TestValidateInput:
    def test_valid_download(self):
        req = _make_request(
            {"case_id": "c1", "identifier": "user1", "description": "test"}
        )
        ok, err, body, form = validate_input(req)
        assert ok is True
        assert form == "download"

    def test_valid_pagination(self):
        req = _make_request(
            {"case_id": "c1", "artifact_id": "a1", "content_type": "post"}
        )
        ok, err, body, form = validate_input(req)
        assert ok is True
        assert form == "pagination"

    def test_missing_required_field(self):
        req = _make_request({"case_id": "c1"})
        ok, err, body, form = validate_input(req)
        assert ok is False
        assert err.status_code == 400

    def test_invalid_json(self):
        req = MagicMock()
        req.get_json.side_effect = ValueError()
        ok, err, body, form = validate_input(req)
        assert ok is False
        assert err.status_code == 400


class TestBuildMetadata:
    def test_processing_excludes_profile(self):
        artifact = {
            "status": "processing",
            "platform": "instagram",
            "identifier": "user1",
            "description": "test",
            "display_name": "User",
            "profile_pic": "pic.jpg",
        }
        meta = _build_metadata(artifact)
        assert "display_name" not in meta
        assert meta["platform"] == "instagram"

    def test_success_includes_profile(self):
        artifact = {
            "status": "success",
            "platform": "instagram",
            "identifier": "user1",
            "description": "test",
            "display_name": "User",
            "profile_pic": "pic.jpg",
        }
        meta = _build_metadata(artifact)
        assert meta["display_name"] == "User"


class TestBuildContents:
    def test_processing_returns_empty(self):
        artifact = {"status": "processing", "contents": [{"caption": "hi"}]}
        assert _build_contents(artifact) == []

    def test_success_returns_contents(self):
        artifact = {
            "status": "success",
            "contents": [
                {
                    "error_message": None,
                    "owners": ["user1"],
                    "caption": "Hello",
                    "datetime": "2024-01-01T12:12:12+00:00",
                    "content_type": "post",
                    "media_content": [
                        {"media_type": "image", "original_url": "http://x.com/1.jpg"}
                    ],
                }
            ],
        }
        result = _build_contents(artifact)
        assert len(result) == 1
        assert result[0]["caption"] == "Hello"


class TestFormatArtifact:
    @patch("function_app.db.get_pagination_cursors", return_value=[])
    def test_basic_format(self, _mock_cursors):
        artifact = {
            "artifact_id": "a1",
            "status": "processing",
            "platform": "instagram",
            "identifier": "user1",
            "description": "test",
        }
        result = _format_artifact(artifact)
        assert result["artifact_id"] == "a1"
        assert result["status"] == "processing"
        assert "metadata" in result
        assert "contents" in result
