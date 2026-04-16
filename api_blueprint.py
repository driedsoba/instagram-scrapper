"""API blueprint for Azure Durable Functions orchestrator and activity functions."""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import azure.durable_functions as df
import requests
from apis.external_api import (
    fetch_profile,
    fetch_posts,
    fetch_reels,
    parse_profile_response,
    parse_posts_response,
    parse_reels_response,
)
import database.db as db

api_bp = df.Blueprint()

BLOBS_DIR = Path(__file__).parent / "blobs"


@api_bp.orchestration_trigger(context_name="context")
def polling_orchestrator(context: df.DurableOrchestrationContext):
    """Orchestrate the initial scraping pipeline: profile, posts, reels."""
    job = json.loads(context.get_input())
    try:
        yield context.call_activity("fetchProfile", job)
        yield context.call_activity("fetchPosts", job)
        yield context.call_activity("fetchReels", job)
        yield context.call_activity("downloadMedia", job)
        yield context.call_activity("updateStatus", {**job, "status": "success"})
    except Exception as e:
        logging.error("polling_orchestrator failed: %s", e)
        yield context.call_activity("updateStatus", {**job, "status": "failed"})
        raise


@api_bp.activity_trigger(input_name="jobInfo")
def fetchProfile(jobInfo):
    """Fetch and store the Instagram profile for an artifact."""
    artifact_id = jobInfo["artifact_id"]
    case_id = jobInfo["case_id"]
    identifier = jobInfo["identifier"]
    logging.info("%s: fetchProfile", artifact_id)
    raw = fetch_profile(identifier)
    parsed = parse_profile_response(raw)
    db.update_metadata_profile(
        artifact_id, parsed["display_name"], parsed["profile_pic"]
    )
    db.update_metadata_status(artifact_id, case_id, "downloading")


@api_bp.activity_trigger(input_name="jobInfo")
def fetchPosts(jobInfo):
    """Fetch the first page of posts and store results and cursor."""
    artifact_id = jobInfo["artifact_id"]
    identifier = jobInfo["identifier"]
    logging.info("%s: fetchPosts", artifact_id)
    raw = fetch_posts(identifier)
    contents, next_max_id = parse_posts_response(raw)
    db.update_results(artifact_id, contents)
    db.upsert_pagination_cursor(
        artifact_id, "post", next_max_id, next_max_id is not None
    )


@api_bp.activity_trigger(input_name="jobInfo")
def fetchReels(jobInfo):
    """Fetch the first page of reels and store results and cursor."""
    artifact_id = jobInfo["artifact_id"]
    identifier = jobInfo["identifier"]
    logging.info("%s: fetchReels", artifact_id)
    raw = fetch_reels(identifier)
    contents, next_max_id = parse_reels_response(raw)
    db.update_results(artifact_id, contents)
    db.upsert_pagination_cursor(
        artifact_id, "reel", next_max_id, next_max_id is not None
    )


@api_bp.orchestration_trigger(context_name="context")
def pagination_orchestrator(context: df.DurableOrchestrationContext):
    """Orchestrate a single pagination fetch for posts or reels."""
    job = json.loads(context.get_input())
    try:
        yield context.call_activity("fetchPage", job)
        yield context.call_activity("downloadMedia", job)
        yield context.call_activity("updateStatus", {**job, "status": "success"})
    except Exception as e:
        logging.error("pagination_orchestrator failed: %s", e)
        yield context.call_activity("updateStatus", {**job, "status": "failed"})
        raise


@api_bp.activity_trigger(input_name="jobInfo")
def fetchPage(jobInfo):
    """Fetch the next page of posts or reels using a stored cursor."""
    artifact_id = jobInfo["artifact_id"]
    identifier = jobInfo["identifier"]
    content_type = jobInfo["content_type"]
    max_id = jobInfo["max_id"]
    logging.info("%s: fetchPage %s (max_id=%s)", artifact_id, content_type, max_id)

    if content_type == "post":
        raw = fetch_posts(identifier, max_id=max_id)
        contents, next_max_id = parse_posts_response(raw)
    elif content_type == "reel":
        raw = fetch_reels(identifier, max_id=max_id)
        contents, next_max_id = parse_reels_response(raw)
    else:
        raise ValueError(f"Invalid content_type: {content_type}")

    db.update_results(artifact_id, contents)
    db.upsert_pagination_cursor(
        artifact_id, content_type, next_max_id, next_max_id is not None
    )


@api_bp.activity_trigger(input_name="jobInfo")
def downloadMedia(jobInfo):
    """Download media files to local blob storage and update DB with blob URLs."""
    artifact_id = jobInfo["artifact_id"]
    logging.info("%s: downloadMedia", artifact_id)

    BLOBS_DIR.mkdir(exist_ok=True)
    contents = db.get_contents_for_artifact(artifact_id)

    for content_doc in contents:
        content_id = content_doc["_id"]
        for idx, mc in enumerate(content_doc.get("media_content", [])):
            blob_fields = {}

            original_url = mc.get("original_url")
            if original_url:
                blob_id, file_path = _download_to_blob(original_url)
                mime = _guess_mime(file_path)
                db.create_blob(blob_id, file_path, mime)
                blob_fields["url"] = f"/api/blob/{blob_id}"

            thumbnail_url = mc.get("original_thumbnail_url")
            if thumbnail_url:
                blob_id, file_path = _download_to_blob(thumbnail_url, suffix="_thumb")
                mime = _guess_mime(file_path)
                db.create_blob(blob_id, file_path, mime)
                blob_fields["thumbnail_url"] = f"/api/blob/{blob_id}"

            if blob_fields:
                db.update_content_media_blob(content_id, idx, blob_fields)


def _download_to_blob(url, suffix=""):
    """Download a URL to the blobs directory. Returns (blob_id, file_path)."""
    blob_id = uuid.uuid4().hex
    ext = _extract_extension(url)
    filename = f"{blob_id}{suffix}{ext}"
    file_path = str(BLOBS_DIR / filename)

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with open(file_path, "wb") as f:
        f.write(resp.content)

    return blob_id, file_path


def _extract_extension(url):
    """Extract file extension from a URL path, defaulting to .jpg."""
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext if ext else ".jpg"


def _guess_mime(file_path):
    """Guess MIME type from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
    }
    return mime_map.get(ext, "application/octet-stream")


@api_bp.activity_trigger(input_name="jobStatus")
def updateStatus(jobStatus):
    """Update the status field of an artifact in the database."""
    artifact_id = jobStatus["artifact_id"]
    case_id = jobStatus["case_id"]
    status = jobStatus["status"]
    logging.info("%s: updateStatus -> %s", artifact_id, status)
    db.update_metadata_status(artifact_id, case_id, status)
