"""
This module defines the database interaction functions for managing artifact metadata and results.
It includes functions for creating artifact metadata, updating results, and updating metadata status.
"""

import logging
import os

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
    logging.info("db:update_metadata_status was triggered")
    pass

def update_results(artifact_id, content):
    logging.info("db:update_results was triggered")
    pass

def create_artifact_metadata(artifact_id, case_id, identifier, description) -> None:
    logging.info("db:create_artifact_metadata was triggered")
    pass

