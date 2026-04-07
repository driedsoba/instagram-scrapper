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
    connection_string = os.environ.get("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017")
    client = MongoClient(connection_string)
    _db = client["instagram_scrapper"]
    logging.info("db:init_db connected to MongoDB")
    return _db


def update_metadata_status(artifact_id, case_id, status):
    db = init_db()
    db["artifacts"].update_one(
        {"_id": artifact_id, "case_id": case_id},
        {"$set": {"status": status}},
    )
    logging.info("db:update_metadata_status artifact %s -> %s", artifact_id, status)


def update_metadata_profile(artifact_id, display_name, profile_pic):
    db = init_db()
    db["artifacts"].update_one(
        {"_id": artifact_id},
        {"$set": {"display_name": display_name, "profile_pic": profile_pic}},
    )
    logging.info("db:update_metadata_profile artifact %s updated profile", artifact_id)

def update_results(artifact_id, contents):
    """Upsert a list of content items into the contents collection."""
    db = init_db()
    for item in contents:
        item_doc = dict(item) if hasattr(item, "__dict__") else item
        item_doc["artifact_id"] = artifact_id
        db["contents"].insert_one(item_doc)
    logging.info("db:update_results inserted %d items for artifact %s", len(contents), artifact_id)

def create_artifact_metadata(artifact_id, case_id, identifier, description) -> None:
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

