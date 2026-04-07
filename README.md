## Available Endpoints

This template has the following endpoints:
- `POST /api/artifact`
  - Takes in `case_id`, `identifier` and `description`
  - returns an `artifact_id`
  - should be idempotent, and execute only once. If the `url` is still processing, it should return the `artifact_id` associated to it. If it is done processing, it can be triggered again as a new search.
  - triggers `polling_orchestrator` in `api_blueprint.py`
- `GET /api/health`
  - returns message `success` if healthy.

### Endpoints to be implemented
- `GET /api/artifacts`
  - To be implemented.
- `GET /api/artifacts/{id}`
  - To be implemented.
- Optional: `GET /api/blob/{id}`
  - To be implemented.

## Local Setup

### Requirements
- [Python 3.10 - 3.13](https://www.python.org/downloads/)
- [Docker / Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Azure Function Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local)

This template uses Azure Durable Functions internally. For Azure Functions to work, you need Python runtime between 3.10 to 3.13. 

Ensure you have python (3.10 - 3.13) installed. Run the following commands to build a virtual environment:
```shell
python -m venv .venv
```
For Windows:
```shell
.venv\Scripts\activate
```
For MacOS/Linux:
```shell
source .venv/bin/activate
```
Install the required packages:
```shell
pip install -r requirements.txt
```

A `local.settings.json` file stores app settings and settings used by local development tools for Azure Functions. You may read more about them [here](https://learn.microsoft.com/en-us/azure/azure-functions/functions-develop-local). Create the file with the following contents:
```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsFeatureFlags": "EnableWorkerIndexing",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true"
  },
}
```

For Durable Functions to work, it requires connection to blob storage. For local testing, we can run a fake Azure Blob using Azureite. We can run Azureite using docker, by running the following command:

```docker
docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite
```

Now you should be able to start the durable function by running the following command:
```shell
func start
```
