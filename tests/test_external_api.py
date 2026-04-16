"""Tests for apis/external_api.py -- response parsers and fetch functions."""

from unittest.mock import MagicMock, patch

import pytest

from apis.external_api import (
    fetch_profile,
    parse_posts_response,
    parse_profile_response,
    parse_reels_response,
)


@pytest.fixture(autouse=True)
def mock_api_key(monkeypatch):
    monkeypatch.setenv("SOCIAVAULT_API_KEY", "test-api-key")


class TestParseProfileResponse:
    def test_basic(self):
        raw = {
            "data": {
                "data": {
                    "user": {
                        "full_name": "Test User",
                        "profile_pic_url_hd": "https://example.com/pic.jpg",
                    }
                }
            }
        }
        result = parse_profile_response(raw)
        assert result["display_name"] == "Test User"
        assert result["profile_pic"] == "https://example.com/pic.jpg"
        assert result["platform"] == "instagram"


class TestParsePostsResponse:
    def test_image_post(self):
        raw = {
            "data": {
                "items": [
                    {
                        "caption": {"text": "Hello world"},
                        "taken_at": 1704067932,
                        "user": {"username": "testuser"},
                        "image_versions2": {
                            "candidates": [{"url": "https://example.com/image.jpg"}]
                        },
                    }
                ],
                "more_available": False,
            }
        }
        contents, next_max_id = parse_posts_response(raw)
        assert len(contents) == 1
        assert contents[0]["caption"] == "Hello world"
        assert contents[0]["content_type"] == "post"
        assert contents[0]["media_content"][0]["media_type"] == "image"
        assert next_max_id is None

    def test_pagination_cursor(self):
        raw = {
            "data": {
                "items": [
                    {
                        "caption": {"text": "Post"},
                        "taken_at": 1704067932,
                        "user": {"username": "testuser"},
                        "image_versions2": {
                            "candidates": [{"url": "https://example.com/1.jpg"}]
                        },
                    }
                ],
                "more_available": True,
                "next_max_id": "abc123",
            }
        }
        _, next_max_id = parse_posts_response(raw)
        assert next_max_id == "abc123"


class TestParseReelsResponse:
    def test_basic(self):
        raw = {
            "data": {
                "items": [
                    {
                        "media": {
                            "caption": {"text": "A reel"},
                            "taken_at": 1704067932,
                            "user": {"username": "reeluser"},
                            "video_versions": [{"url": "https://example.com/reel.mp4"}],
                            "image_versions2": {
                                "candidates": [
                                    {"url": "https://example.com/reel_thumb.jpg"}
                                ]
                            },
                        }
                    }
                ],
                "paging_info": {
                    "more_available": True,
                    "max_id": "reel_cursor_123",
                },
            }
        }
        contents, next_max_id = parse_reels_response(raw)
        assert len(contents) == 1
        assert contents[0]["content_type"] == "reel"
        assert contents[0]["media_content"][0]["media_type"] == "video"
        assert next_max_id == "reel_cursor_123"


class TestFetchProfile:
    @patch("apis.external_api.requests.get")
    def test_calls_api_with_correct_params(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {}}
        mock_get.return_value = mock_resp

        fetch_profile("testuser")

        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["X-API-Key"] == "test-api-key"
        assert kwargs["params"]["handle"] == "testuser"
