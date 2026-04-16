"""Tests for api_blueprint.py -- activity error handling."""

from unittest.mock import patch

from api_blueprint import fetchPosts, fetchProfile, fetchReels


class TestFetchProfileActivity:
    @patch("api_blueprint.db")
    @patch("api_blueprint.fetch_profile", side_effect=Exception("API error"))
    def test_continues_on_api_failure(self, _mock_fetch, mock_db):
        fetchProfile({"artifact_id": "a1", "case_id": "c1", "identifier": "user1"})
        mock_db.update_metadata_profile.assert_not_called()
        mock_db.update_metadata_status.assert_called_once_with(
            "a1", "c1", "downloading"
        )


class TestFetchPostsActivity:
    @patch("api_blueprint.db")
    @patch("api_blueprint.fetch_posts", side_effect=Exception("API error"))
    def test_stores_error_on_failure(self, _mock_fetch, mock_db):
        fetchPosts({"artifact_id": "a1", "identifier": "user1"})
        args = mock_db.update_results.call_args
        assert args[0][1][0]["error_message"] == "Failed to fetch posts"
        assert args[0][1][0]["content_type"] == "post"
        mock_db.upsert_pagination_cursor.assert_not_called()


class TestFetchReelsActivity:
    @patch("api_blueprint.db")
    @patch("api_blueprint.fetch_reels", side_effect=Exception("API error"))
    def test_stores_error_on_failure(self, _mock_fetch, mock_db):
        fetchReels({"artifact_id": "a1", "identifier": "user1"})
        args = mock_db.update_results.call_args
        assert args[0][1][0]["error_message"] == "Failed to fetch reels"
        assert args[0][1][0]["content_type"] == "reel"
