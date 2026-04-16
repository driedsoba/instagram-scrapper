import azure.functions as func
import azure.durable_functions as df
import database.db as db
import json
import os
import uuid
from api_blueprint import api_bp
import logging

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s.%(msecs)03d:%(name)s:%(levelname)s| %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
console_handler.setFormatter(formatter)

logging.getLogger().addHandler(console_handler)

app = df.DFApp()

app.register_blueprint(api_bp)


def error_response(response, status_code):
    """Build a JSON error HttpResponse from a message string or raw bytes."""
    if isinstance(response, bytes):
        payload = response
    else:
        payload = json.dumps({"message": response})
    return func.HttpResponse(
        payload, status_code=status_code, mimetype="application/json"
    )


def validate_input(req) -> tuple[bool, None | func.HttpResponse, dict, str]:
    """Parse POST body and return (ok, error_resp, body, form_type).

    form_type is 'download' or 'pagination'.
    """
    try:
        body = req.get_json()
    except ValueError:
        return False, error_response("Invalid request body", 400), {}, ""

    if not isinstance(body, dict):
        return False, error_response("Invalid request body", 400), {}, ""

    case_id = body.get("case_id")
    if not case_id:
        return (
            False,
            error_response("Invalid request body, missing 'case_id'.", 400),
            {},
            "",
        )

    # Pagination form: {case_id, artifact_id, content_type}
    if body.get("artifact_id") and body.get("content_type"):
        return (
            True,
            None,
            {
                "case_id": case_id,
                "artifact_id": body["artifact_id"],
                "content_type": body["content_type"],
            },
            "pagination",
        )

    # New download form: {case_id, identifier, description}
    for field in ("identifier", "description"):
        if not body.get(field):
            return (
                False,
                error_response(f"Invalid request body, missing '{field}'.", 400),
                {},
                "",
            )

    return (
        True,
        None,
        {
            "case_id": case_id,
            "identifier": body["identifier"],
            "description": body["description"],
        },
        "download",
    )


@app.route(route="artifacts", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
@app.durable_client_input(client_name="client")
async def trigger_download(
    req: func.HttpRequest, client: df.DurableOrchestrationClient
) -> func.HttpResponse:
    """Handle POST /api/artifacts for new downloads and pagination requests."""
    logging.info("POST /api/artifacts")
    try:
        valid, error_resp, body, form = validate_input(req)
        if not valid:
            return error_resp

        if form == "pagination":
            artifact_id = body["artifact_id"]
            case_id = body["case_id"]
            content_type = body["content_type"]

            if content_type not in ("post", "reel"):
                return error_response(
                    "Invalid content_type. Must be 'post' or 'reel'.", 400
                )

            artifact = db.get_artifact_metadata(artifact_id)
            if not artifact or artifact.get("case_id") != case_id:
                return error_response("Artifact not found.", 404)

            claimed = db.claim_pagination_cursor(artifact_id, content_type, None)
            if not claimed:
                cursor = db.get_pagination_cursor(artifact_id, content_type)
                if not cursor or not cursor.get("has_more"):
                    return error_response(
                        f"No more pages available for content_type '{content_type}'.",
                        400,
                    )
                claimed = db.claim_pagination_cursor(
                    artifact_id, content_type, cursor["next_cursor"]
                )
                if not claimed:
                    return error_response(
                        f"No more pages available for content_type '{content_type}'.",
                        400,
                    )

            await client.start_new(
                "pagination_orchestrator",
                client_input=json.dumps(
                    {
                        "artifact_id": artifact_id,
                        "case_id": case_id,
                        "identifier": artifact.get("identifier"),
                        "content_type": content_type,
                        "max_id": claimed["next_cursor"],
                    }
                ),
            )

            return func.HttpResponse(
                json.dumps({"artifact_id": artifact_id}),
                status_code=202,
                mimetype="application/json",
            )

        case_id = body["case_id"]
        identifier = body["identifier"]
        description = body["description"]

        artifact_id = uuid.uuid4().hex
        artifact_id, created = db.claim_or_get_active_artifact(
            artifact_id, case_id, identifier, description
        )

        if not created:
            return func.HttpResponse(
                json.dumps({"artifact_id": artifact_id}),
                status_code=200,
                mimetype="application/json",
            )

        await client.start_new(
            "polling_orchestrator",
            client_input=json.dumps(
                {
                    "artifact_id": artifact_id,
                    "case_id": case_id,
                    "identifier": identifier,
                }
            ),
        )

        return func.HttpResponse(
            json.dumps({"artifact_id": artifact_id}),
            status_code=202,
            mimetype="application/json",
        )

    except Exception:
        logging.exception("POST /api/artifacts failed")
        return error_response("Internal server error.", 500)


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
async def healthcheck(req: func.HttpRequest) -> func.HttpResponse:
    """Return a simple health-check response."""
    return func.HttpResponse(
        json.dumps({"message": "success"}), status_code=200, mimetype="application/json"
    )


def _build_metadata(artifact):
    """Build the metadata dict for an artifact based on its status."""
    status = artifact.get("status")
    base = {
        "platform": artifact.get("platform"),
        "identifier": artifact.get("identifier"),
        "description": artifact.get("description"),
    }
    if status in ("processing", "downloading"):
        return base
    return {
        **base,
        "display_name": artifact.get("display_name"),
        "profile_pic": artifact.get("profile_pic"),
    }


def _build_media_content(item):
    """Build the media_content list for a single content item."""
    media = []
    for mc in item.get("media_content", []):
        entry = {
            "media_type": mc.get("media_type"),
            "original_url": mc.get("original_url"),
        }
        if mc.get("media_type") == "video":
            entry["original_thumbnail_url"] = mc.get("original_thumbnail_url")
        if mc.get("url"):
            entry["url"] = mc["url"]
        if mc.get("thumbnail_url"):
            entry["thumbnail_url"] = mc["thumbnail_url"]
        media.append(entry)
    return media


def _build_contents(artifact):
    """Build the contents list for an artifact, empty if still processing."""
    if artifact.get("status") in ("processing", "downloading"):
        return []
    return [
        {
            "error_message": item.get("error_message"),
            "owners": item.get("owners"),
            "caption": item.get("caption"),
            "datetime": item.get("datetime"),
            "content_type": item.get("content_type"),
            "media_content": _build_media_content(item),
        }
        for item in artifact.get("contents", [])
    ]


def _build_has_more_data(cursors):
    """Build has_more_data list from pre-fetched cursor docs."""
    return [
        {"content_type": c["content_type"], "has_more_data": c.get("has_more", False)}
        for c in cursors
    ]


def _format_artifact(artifact, cursors=None):
    """Format an artifact document into the API response shape."""
    result = {
        "artifact_id": artifact.get("artifact_id"),
        "status": artifact.get("status"),
        "metadata": _build_metadata(artifact),
        "contents": _build_contents(artifact),
    }
    if cursors is None:
        cursors = db.get_pagination_cursors(artifact.get("artifact_id"))
    has_more = _build_has_more_data(cursors)
    if has_more:
        result["has_more_data"] = has_more
    return result


@app.route(route="artifacts", auth_level=func.AuthLevel.FUNCTION, methods=["GET"])
async def get_artifacts(req: func.HttpRequest) -> func.HttpResponse:
    """Handle GET /api/artifacts -- return all artifacts as a JSON array."""
    logging.info("GET /api/artifacts")
    try:
        artifacts = db.get_all_artifacts()
        artifact_ids = [a.get("artifact_id") for a in artifacts]
        cursors_map = db.get_pagination_cursors_batch(artifact_ids)
        result = [
            _format_artifact(a, cursors_map.get(a.get("artifact_id"), []))
            for a in artifacts
        ]
        return func.HttpResponse(
            json.dumps(result), status_code=200, mimetype="application/json"
        )
    except Exception:
        logging.exception("GET /api/artifacts failed")
        return error_response("Internal server error.", 500)


@app.route(
    route="artifacts/{artifact_id}",
    auth_level=func.AuthLevel.FUNCTION,
    methods=["GET"],
)
async def get_artifact(req: func.HttpRequest) -> func.HttpResponse:
    """Handle GET /api/artifacts/{id} -- return a single artifact or 404."""
    artifact_id = req.route_params.get("artifact_id")
    logging.info("GET /api/artifacts/%s", artifact_id)
    try:
        artifact = db.get_artifact(artifact_id)
        if not artifact:
            return error_response("Artifact not found.", 404)
        return func.HttpResponse(
            json.dumps(_format_artifact(artifact)),
            status_code=200,
            mimetype="application/json",
        )
    except Exception:
        logging.exception("GET /api/artifacts/%s failed", artifact_id)
        return error_response("Internal server error.", 500)


@app.route(
    route="blob/{blob_id}",
    auth_level=func.AuthLevel.FUNCTION,
    methods=["GET"],
)
async def get_blob(req: func.HttpRequest) -> func.HttpResponse:
    """Handle GET /api/blob/{blob_id} -- serve a stored media file."""
    blob_id = req.route_params.get("blob_id")
    logging.info("GET /api/blob/%s", blob_id)
    try:
        blob = db.get_blob(blob_id)
        if not blob:
            return error_response("Blob not found.", 404)

        file_path = os.path.normpath(os.path.abspath(blob["file_path"]))
        trusted_dir = os.path.normpath(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "blobs"))
        )
        if os.path.commonpath([trusted_dir, file_path]) != trusted_dir:
            return error_response("Blob file not found.", 404)

        if not os.path.isfile(file_path):
            return error_response("Blob file not found.", 404)

        def _stream_file(path, chunk_size=65536):
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        return func.HttpResponse(
            body=b"".join(_stream_file(file_path)),
            status_code=200,
            mimetype=blob.get("content_type", "application/octet-stream"),
        )
    except Exception:
        logging.exception("GET /api/blob/%s failed", blob_id)
        return error_response("Internal server error.", 500)
