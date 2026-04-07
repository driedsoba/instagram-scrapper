"""
This module defines the API blueprint for Azure Durable Functions, including orchestrator and activity functions.
It handles the orchestration of long-running processes, including triggering external API call and updating results and status in the database.
"""
import traceback
import azure.durable_functions as df
import json
import logging
from apis import external_api
from exceptions import APIException
import database.db as db

api_bp = df.Blueprint()


def activity_result_output(success, error_message, results=None):
    return {
        "success": success,
        "error_message": str(error_message),
        "results": results,
    } if results else {
        "success": success,
        "error_message": str(error_message)
    }

def invalid_execution(results):
    success = results["success"]
    if not success:
        return results["error_message"]
    return None


@api_bp.orchestration_trigger(context_name="context")
def polling_orchestrator(context: df.DurableOrchestrationContext):
    job = json.loads(context.get_input())
    case_info = {"artifact_id": job.get("artifact_id"), "case_id": job.get("case_id"), "identifier": job.get("identifier") }

    
    results = yield context.call_activity(startJob, job) # output of activity_result_output

    if error := invalid_execution(results):
        job_status = case_info | {"status": "failed"}
        yield context.call_activity(updateStatus, job_status)
        return error

    job_status = case_info | {"status": "success"}
    yield context.call_activity(updateStatus, job_status)

    return "All tasks completed."


@api_bp.activity_trigger(input_name="jobInfo")
def startJob(jobInfo):
    artifact_id = jobInfo.get("artifact_id")
    case_id = jobInfo.get("case_id")
    identifier = jobInfo.get("identifier")
    processing = True
    logging.info(f"{artifact_id}:startJob")
    while processing:
        logging.info(f"{artifact_id}:calling API")
        try:
            resp = external_api.trigger_external(identifier, case_id, artifact_id)
            if resp["status"] == "success":
                results = db.update_results(artifact_id, resp["results"])
                processing = False
                return activity_result_output(True, None, results)
            else:
                status = resp["status"]
                raise APIException("API call failed.", 500, status, resp.get("error_message", ""))
        except Exception as e:
            logging.error(f"{artifact_id}: startJobError: {e}")
            traceback.print_exception(e)
            return activity_result_output(False, e, None)
        

@api_bp.activity_trigger(input_name="jobStatus")
def updateStatus(jobStatus):
    artifact_id = jobStatus.get("artifact_id")
    case_id = jobStatus.get("case_id")
    status = jobStatus.get("status")
    try:
        db.update_metadata_status(artifact_id, case_id, status)
        return activity_result_output(True, f"{artifact_id}: updateStatus: Success")
    except Exception as e:
        logging.error(f"{artifact_id}: updateStatus: {e}")
        return activity_result_output(False, f"{artifact_id}: updateStatus: {e}")
