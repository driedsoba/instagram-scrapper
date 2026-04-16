import azure.functions as func
import azure.durable_functions as df
import database.db as db
import json
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
    logging.info("POST /api/artifacts")
    try:
        valid, error_resp, body, form = validate_input(req)
        if not valid:
            return error_resp

        if form == "pagination":
            # Stub: full implementation in Issue #5
            return error_response("Pagination not yet implemented.", 501)

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

    except Exception as e:
        logging.error(e)
        return error_response("Internal server error.", 500)


@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
async def healthcheck(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"message": "success"}), status_code=200, mimetype="application/json"
    )


def _build_metadata(artifact):
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
    media = []
    for mc in item.get("media_content", []):
        entry = {
            "media_type": mc.get("media_type"),
            "original_url": mc.get("original_url"),
        }
        if mc.get("media_type") == "video":
            entry["original_thumbnail_url"] = mc.get("original_thumbnail_url")
        media.append(entry)
    return media


def _build_contents(artifact):
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


def _format_artifact(artifact):
    return {
        "artifact_id": artifact.get("artifact_id"),
        "status": artifact.get("status"),
        "metadata": _build_metadata(artifact),
        "contents": _build_contents(artifact),
    }


@app.route(route="artifacts", auth_level=func.AuthLevel.FUNCTION, methods=["GET"])
async def get_artifacts(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("GET /api/artifacts")
    try:
        artifacts = db.get_all_artifacts()
        result = [_format_artifact(a) for a in artifacts]
        return func.HttpResponse(
            json.dumps(result), status_code=200, mimetype="application/json"
        )
    except Exception as e:
        logging.error(e)
        return error_response("Internal server error.", 500)


@app.route(
    route="artifacts/{artifact_id}",
    auth_level=func.AuthLevel.FUNCTION,
    methods=["GET"],
)
async def get_artifact(req: func.HttpRequest) -> func.HttpResponse:
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
    except Exception as e:
        logging.error(e)
        return error_response("Internal server error.", 500)
