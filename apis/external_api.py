"""
This module defines the external API controller logic for processing requests and returning results.
It includes functions for triggering external API calls, handling responses.
"""

import time
import requests
import logging

# Controller logic
def trigger_external(identifier, case_id, artifact_id):
    logging.info("external_api:trigger_external was triggered")
    time.sleep(5) # Simulate processing time
    return {
        "status": "success",
        "results": {
            "identifier": identifier,
            "case_id": case_id,
            "artifact_id": artifact_id,
        }
    }