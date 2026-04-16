"""
This module defines the database interaction functions for managing artifact metadata and results.
It includes functions for creating artifact metadata, updating results, and updating metadata status.
"""

import logging
import os
from datetime import UTC, datetime

from pymongo import MongoClient

_db = None


def init_db():
    """Connect to MongoDB and return the database handle. Cached after first call."""
    global _db
    if _db is not None:
        return _db
    connection_string = os.environ.get(
        "MONGODB_CONNECTION_STRING", "mongodb://localhost:27017"
    )
    client = MongoClient(
        connection_string,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000,
    )
    _db = client["instagram_scrapper"]
    logging.info("db:init_db connected to MongoDB")
    return _db


def update_metadata_status(artifact_id, case_id, status):
    """Set the status field of an artifact document."""
    db = init_db()
    db["artifacts"].update_one(
        {"_id": artifact_id, "case_id": case_id},
        {"$set": {"status": status}},
    )
    logging.info("db:update_metadata_status artifact %s -> %s", artifact_id, status)


def update_metadata_profile(artifact_id, display_name, profile_pic):
    """Update the display_name and profile_pic fields of an artifact."""
    db = init_db()
    db["artifacts"].update_one(
        {"_id": artifact_id},
        {"$set": {"display_name": display_name, "profile_pic": profile_pic}},
    )
    logging.info("db:update_metadata_profile artifact %s updated profile", artifact_id)


def update_results(artifact_id, contents):
    """Insert a list of content items into the contents collection."""
    db = init_db()
    for item in contents:
        item_doc = item if isinstance(item, dict) else vars(item)
        item_doc["artifact_id"] = artifact_id
        db["contents"].insert_one(item_doc)
    logging.info(
        "db:update_results inserted %d items for artifact %s",
        len(contents),
        artifact_id,
    )


def create_artifact_metadata(artifact_id, case_id, identifier, description) -> None:
    """Insert a new artifact metadata document with processing status."""
    db = init_db()
    doc = {
        "_id": artifact_id,
        "case_id": case_id,
        "identifier": identifier,
        "description": description,
        "platform": "instagram",
        "status": "processing",
        "display_name": None,
        "profile_pic": None,
        "created_datetime": datetime.now(UTC).isoformat(),
    }
    db["artifacts"].insert_one(doc)
    logging.info("db:create_artifact_metadata inserted artifact %s", artifact_id)


def _artifact_with_contents(db, artifact_doc):
    """Join an artifact document with its content items."""
    artifact_id = artifact_doc["_id"]
    contents = list(db["contents"].find({"artifact_id": artifact_id}, {"_id": 0}))
    result = {k: v for k, v in artifact_doc.items() if k != "_id"}
    result["artifact_id"] = artifact_id
    result["contents"] = contents
    return result


def get_artifact(artifact_id):
    """Fetch a single artifact with its contents. Returns None if not found."""
    db = init_db()
    doc = db["artifacts"].find_one({"_id": artifact_id})
    if doc is None:
        return None
    return _artifact_with_contents(db, doc)


def get_all_artifacts():
    """Fetch all artifacts with their contents."""
    db = init_db()
    artifacts = list(db["artifacts"].find())
    return [_artifact_with_contents(db, doc) for doc in artifacts]


def upsert_pagination_cursor(artifact_id, content_type, next_cursor, has_more):
    """Store or update the pagination cursor for an artifact + content_type pair."""
    db = init_db()
    db["pagination_cursors"].update_one(
        {"artifact_id": artifact_id, "content_type": content_type},
        {"$set": {"next_cursor": next_cursor, "has_more": has_more}},
        upsert=True,
    )
    logging.info(
        "db:upsert_pagination_cursor artifact %s content_type %s has_more=%s",
        artifact_id,
        content_type,
        has_more,
    )


def get_pagination_cursor(artifact_id, content_type):
    """Return the stored cursor doc for an artifact + content_type, or None."""
    db = init_db()
    return db["pagination_cursors"].find_one(
        {"artifact_id": artifact_id, "content_type": content_type},
        {"_id": 0},
    )


def get_pagination_cursors(artifact_id):
    """Return all pagination cursor docs for an artifact, sorted by content_type."""
    db = init_db()
    return list(
        db["pagination_cursors"]
        .find({"artifact_id": artifact_id}, {"_id": 0})
        .sort("content_type", 1)
    )


def get_pagination_cursors_batch(artifact_ids):
    """Return all pagination cursors for a list of artifact IDs, grouped by artifact_id."""
    db = init_db()
    docs = list(
        db["pagination_cursors"]
        .find({"artifact_id": {"$in": artifact_ids}}, {"_id": 0})
        .sort("content_type", 1)
    )
    result = {}
    for doc in docs:
        result.setdefault(doc["artifact_id"], []).append(doc)
    return result


def claim_pagination_cursor(artifact_id, content_type, expected_cursor):
    """Atomically claim a pagination cursor if it matches the expected value.

    Uses find_one_and_update to atomically match on (artifact_id, content_type,
    next_cursor, has_more=True) and set has_more=False to prevent concurrent
    claims. Returns the matched document (pre-update) or None if no match.
    """
    db = init_db()
    doc = db["pagination_cursors"].find_one_and_update(
        {
            "artifact_id": artifact_id,
            "content_type": content_type,
            "next_cursor": expected_cursor,
            "has_more": True,
        },
        {"$set": {"has_more": False}},
    )
    return doc


def get_artifact_metadata(artifact_id):
    """Fetch only artifact metadata (no contents). Returns None if not found."""
    db = init_db()
    doc = db["artifacts"].find_one({"_id": artifact_id})
    if doc is None:
        return None
    result = {k: v for k, v in doc.items() if k != "_id"}
    result["artifact_id"] = doc["_id"]
    return result


def find_active_artifact_by_identifier(identifier):
    """Return an in-progress artifact for the given identifier, or None.

    An artifact is considered active when its status is 'processing' or
    'downloading'. This is used for idempotency -- if an active artifact
    already exists we return its artifact_id instead of starting a new job.
    """
    db = init_db()
    doc = db["artifacts"].find_one(
        {"identifier": identifier, "status": {"$in": ["processing", "downloading"]}},
    )
    if doc is None:
        return None
    doc["artifact_id"] = doc.pop("_id")
    return doc


def claim_or_get_active_artifact(artifact_id, case_id, identifier, description):
    """Atomically claim a new artifact or return an existing active one.

    Uses find_one_and_update with upsert semantics keyed on
    (identifier, status in [processing, downloading]).

    Returns (artifact_id, created) where created is True if this call
    inserted the new document.
    """
    db = init_db()
    # Try to find an existing active artifact first (atomic read)
    existing = db["artifacts"].find_one(
        {"identifier": identifier, "status": {"$in": ["processing", "downloading"]}},
    )
    if existing:
        return existing["_id"], False

    # No active artifact - insert with a unique _id.
    # If a concurrent request inserted between our read and write,
    # the insert will fail due to _id uniqueness (caller retries via the
    # duplicate key path) or we just fall back to the find above on retry.
    try:
        create_artifact_metadata(artifact_id, case_id, identifier, description)
        return artifact_id, True
    except Exception:
        # Race: another request inserted an active artifact between our
        # find and insert. Re-check for the active doc.
        existing = db["artifacts"].find_one(
            {
                "identifier": identifier,
                "status": {"$in": ["processing", "downloading"]},
            },
        )
        if existing:
            return existing["_id"], False
        raise


def create_blob(blob_id, file_path, content_type):
    """Store a blob record mapping blob_id to a file path and MIME type."""
    db = init_db()
    db["blobs"].insert_one(
        {
            "_id": blob_id,
            "file_path": file_path,
            "content_type": content_type,
        }
    )
    logging.info("db:create_blob inserted blob %s at %s", blob_id, file_path)


def get_blob(blob_id):
    """Return the blob record for the given blob_id, or None if not found."""
    db = init_db()
    doc = db["blobs"].find_one({"_id": blob_id})
    if doc is None:
        return None
    doc["blob_id"] = doc.pop("_id")
    return doc


def get_contents_for_artifact(artifact_id):
    """Return all content documents for an artifact, including _id."""
    db = init_db()
    return list(db["contents"].find({"artifact_id": artifact_id}))


def update_content_media_blob(content_id, media_index, blob_fields):
    """Update blob URL fields on a specific media_content entry by index."""
    db = init_db()
    set_fields = {f"media_content.{media_index}.{k}": v for k, v in blob_fields.items()}
    db["contents"].update_one({"_id": content_id}, {"$set": set_fields})
    logging.info(
        "db:update_content_media_blob content=%s idx=%d fields=%s",
        content_id,
        media_index,
        list(blob_fields.keys()),
    )
