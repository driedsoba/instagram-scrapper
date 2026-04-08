"""
This module defines the external API controller logic for processing requests and returning results.
It includes functions for calling the SociaVault API and parsing responses into spec format.
"""

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
    response = requests.get(url, headers=headers, params=params, timeout=30)
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