"""
This module defines the external API controller logic for processing requests and returning results.
It includes functions for calling the SociaVault API and parsing responses into spec format.
"""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import requests

BASE_URL = "https://api.sociavault.com/v1/scrape/instagram"


def _get_api_key():
    """Load and validate the SociaVault API key from environment."""
    key = os.environ.get("SOCIAVAULT_API_KEY")
    if not key:
        raise ValueError("SOCIAVAULT_API_KEY environment variable is not set")
    return key


def _make_request(endpoint, params):
    """Make an authenticated GET request to SociaVault and return the JSON response."""
    headers = {"X-API-Key": _get_api_key()}
    url = f"{BASE_URL}/{endpoint}"
    response = requests.get(url, headers=headers, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def fetch_profile(identifier):
    """Fetch Instagram profile data from SociaVault."""
    logging.info("external_api:fetch_profile for %s", identifier)
    return _make_request("profile", {"handle": identifier})


def fetch_posts(identifier, max_id=None):
    """Fetch Instagram posts from SociaVault. Optionally pass max_id for pagination."""
    logging.info("external_api:fetch_posts for %s (max_id=%s)", identifier, max_id)
    params = {"handle": identifier}
    if max_id is not None:
        params["max_id"] = max_id
    return _make_request("posts", params)


def fetch_reels(identifier, max_id=None):
    """Fetch Instagram reels from SociaVault. Optionally pass max_id for pagination."""
    logging.info("external_api:fetch_reels for %s (max_id=%s)", identifier, max_id)
    params = {"handle": identifier}
    if max_id is not None:
        params["max_id"] = max_id
    return _make_request("reels", params)


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------


def _as_list(obj) -> list:
    """Normalize a value that may be a dict-with-string-keys (SociaVault quirk) into a list."""
    if isinstance(obj, dict):
        return list(obj.values())
    if isinstance(obj, list):
        return obj
    return []


def parse_profile_response(raw: dict) -> dict:
    """Parse SociaVault profile response into spec metadata fields.

    Returns dict with display_name, profile_pic, and platform.
    """
    user = raw.get("data", {}).get("data", {}).get("user", {})
    return {
        "display_name": user.get("full_name"),
        "profile_pic": user.get("profile_pic_url_hd"),
        "platform": "instagram",
    }


def _parse_media_item(item: dict) -> dict:
    """Parse a single post/carousel child into a MediaContent-compatible dict."""
    has_video = bool(item.get("video_versions"))
    media_type = "video" if has_video else "image"

    candidates = _as_list(item.get("image_versions2", {}).get("candidates"))

    if has_video:
        video_versions = _as_list(item.get("video_versions"))
        original_url = video_versions[0]["url"] if video_versions else ""
        original_thumbnail_url = candidates[0].get("url") if candidates else None
    else:
        original_url = candidates[0].get("url", "") if candidates else ""
        original_thumbnail_url = None

    return {
        "media_type": media_type,
        "original_url": original_url,
        "original_thumbnail_url": original_thumbnail_url,
    }


def _parse_post_item(item: dict) -> dict:
    """Parse a single SociaVault post item into an ArtifactContent-compatible dict."""
    caption_obj = item.get("caption")
    caption = caption_obj.get("text") if isinstance(caption_obj, dict) else None

    taken_at = item.get("taken_at")
    dt = datetime.fromtimestamp(taken_at, tz=UTC).isoformat() if taken_at else None

    user = item.get("user", {})
    owners = [user["username"]] if user.get("username") else []

    # Carousel posts contain multiple media children
    carousel = _as_list(item.get("carousel_media"))
    if carousel:
        media_content = [_parse_media_item(child) for child in carousel]
    else:
        media_content = [_parse_media_item(item)]

    return {
        "owners": owners,
        "caption": caption,
        "datetime": dt,
        "content_type": "post",
        "media_content": media_content,
    }


def parse_posts_response(raw: dict) -> tuple[list[dict], str | None]:
    """Parse SociaVault posts response.

    Returns (contents, next_max_id) where contents is a list of
    ArtifactContent-compatible dicts and next_max_id is the pagination
    cursor (None if no more pages).
    """
    data = raw.get("data", {})
    raw_items = data.get("items", {})
    items = list(raw_items.values()) if isinstance(raw_items, dict) else raw_items
    contents = [_parse_post_item(item) for item in items]

    next_max_id = None
    if data.get("more_available"):
        next_max_id = data.get("next_max_id")

    return contents, next_max_id


def parse_reels_response(raw: dict) -> tuple[list[dict], str | None]:
    """Parse SociaVault reels response.

    Returns (contents, next_max_id) where contents is a list of
    ArtifactContent-compatible dicts and next_max_id is the pagination cursor.
    """
    data = raw.get("data", {})
    raw_items = data.get("items", {})
    items = list(raw_items.values()) if isinstance(raw_items, dict) else raw_items
    contents = []

    for item in items:
        caption_obj = item.get("caption")
        caption = caption_obj.get("text") if isinstance(caption_obj, dict) else None

        taken_at = item.get("taken_at")
        dt = datetime.fromtimestamp(taken_at, tz=UTC).isoformat() if taken_at else None

        user = item.get("user", {})
        owners = [user["username"]] if user.get("username") else []

        video_versions = _as_list(item.get("video_versions"))
        video_url = video_versions[0].get("url", "") if video_versions else ""
        candidates = _as_list(item.get("image_versions2", {}).get("candidates"))
        thumbnail_url = candidates[0].get("url") if candidates else None

        contents.append({
            "owners": owners,
            "caption": caption,
            "datetime": dt,
            "content_type": "reel",
            "media_content": [{
                "media_type": "video",
                "original_url": video_url,
                "original_thumbnail_url": thumbnail_url,
            }],
        })

    paging_info = data.get("paging_info", {})
    next_max_id = paging_info.get("max_id") if paging_info.get("more_available", False) else None

    return contents, next_max_id