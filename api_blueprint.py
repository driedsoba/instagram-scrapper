"""API blueprint for Azure Durable Functions orchestrator and activity functions."""

from __future__ import annotations

import json
import logging

import azure.durable_functions as df
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


@api_bp.orchestration_trigger(context_name="context")
def polling_orchestrator(context: df.DurableOrchestrationContext):
    job = json.loads(context.get_input())
    try:
        yield context.call_activity("fetchProfile", job)
        yield context.call_activity("fetchPosts", job)
        yield context.call_activity("fetchReels", job)
        yield context.call_activity("updateStatus", {**job, "status": "success"})
    except Exception as e:
        logging.error("polling_orchestrator failed: %s", e)
        yield context.call_activity("updateStatus", {**job, "status": "failed"})
        raise


@api_bp.activity_trigger(input_name="jobInfo")
def fetchProfile(jobInfo):
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
    job = json.loads(context.get_input())
    try:
        yield context.call_activity("fetchPage", job)
        yield context.call_activity("updateStatus", {**job, "status": "success"})
    except Exception as e:
        logging.error("pagination_orchestrator failed: %s", e)
        yield context.call_activity("updateStatus", {**job, "status": "failed"})
        raise


@api_bp.activity_trigger(input_name="jobInfo")
def fetchPage(jobInfo):
    artifact_id = jobInfo["artifact_id"]
    identifier = jobInfo["identifier"]
    content_type = jobInfo["content_type"]
    max_id = jobInfo["max_id"]
    logging.info("%s: fetchPage %s (max_id=%s)", artifact_id, content_type, max_id)

    if content_type == "post":
        raw = fetch_posts(identifier, max_id=max_id)
        contents, next_max_id = parse_posts_response(raw)
    else:
        raw = fetch_reels(identifier, max_id=max_id)
        contents, next_max_id = parse_reels_response(raw)

    db.update_results(artifact_id, contents)
    db.upsert_pagination_cursor(
        artifact_id, content_type, next_max_id, next_max_id is not None
    )


@api_bp.activity_trigger(input_name="jobStatus")
def updateStatus(jobStatus):
    artifact_id = jobStatus["artifact_id"]
    case_id = jobStatus["case_id"]
    status = jobStatus["status"]
    logging.info("%s: updateStatus -> %s", artifact_id, status)
    db.update_metadata_status(artifact_id, case_id, status)
