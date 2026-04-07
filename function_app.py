import azure.functions as func
import azure.durable_functions as df
import database.db as db
import json
import uuid
from api_blueprint import api_bp
import logging

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s.%(msecs)03d:%(name)s:%(levelname)s| %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(formatter)

logging.getLogger().addHandler(console_handler)

app = df.DFApp()

app.register_blueprint(api_bp)

def error_response(response, status_code):
    if type(response) == bytes:
        payload = response
    else:
        payload = json.dumps({"message": response})
    return func.HttpResponse(
            payload,
            status_code=status_code,
            mimetype="application/json"
        )

def validate_input(req, expectedFields) -> tuple[bool, None | func.HttpResponse, dict]:
    try:
        request_body = req.get_json()
    except ValueError:
        return False, error_response("Invalid request body", 400), {}
    
    req_body = {}

    for expectedField in expectedFields:
        value = request_body.get(expectedField, -1)
        if value == -1:
            return False, error_response(f"Invalid request body, missing '{expectedField}'.", 400), {}
        else:
            req_body[expectedField] = value
    return True, None, req_body

async def _trigger_download(client, artifact_id, case_id, identifier, description):

    db.create_artifact_metadata(artifact_id, case_id, identifier, description)

    await client.start_new('polling_orchestrator', client_input=json.dumps({
        "artifact_id": artifact_id,
        "case_id": case_id,
        "identifier": identifier,
    }))

    return artifact_id

@app.route(route="artifacts", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
@app.durable_client_input(client_name="client")
async def trigger_download(req: func.HttpRequest, client: df.DurableOrchestrationClient) -> func.HttpResponse:
    logging.info("Python HTTP artifact function processed a request.")
    try:
        valid, error_resp, body = validate_input(req, ["case_id", "identifier", "description"])
        if not valid:
            return error_resp
        
        case_id = body["case_id"]
        identifier = body["identifier"]
        description = body["description"]

        artifact_id = uuid.uuid4().hex

        artifact_id = await _trigger_download(client, artifact_id, case_id, identifier, description)

        return func.HttpResponse(
                json.dumps({"artifact_id": artifact_id}),
                status_code=200,
                mimetype="application/json"
        )

    except Exception as e:
        logging.error(e)
        return error_response("Internal server error.", 500)
    
@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
async def healthcheck(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"message" : "success"}),
        status_code=200,
        mimetype="application/json"
    )