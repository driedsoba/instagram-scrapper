# Instagram Scrapper

An Azure Durable Functions application that scrapes Instagram profiles, posts, and reels via the [SociaVault](https://sociavault.com/) API. It downloads media files and stores metadata in MongoDB.

## Design Considerations

- **Non-blocking orchestration** - `POST /api/artifacts` returns immediately with an `artifact_id`. The scraping pipeline runs asynchronously via Azure Durable Functions. Clients poll `GET /api/artifacts/{id}` to check progress.
- **Idempotent downloads** - If the same Instagram handle is already being processed, the existing `artifact_id` is returned instead of starting a duplicate job.
- **Extensible to other platforms** - The SociaVault API client and database layer are structured so that additional social media platforms can be integrated without changing the orchestrator or endpoint logic.
- **Containerized** - Ships with a Dockerfile for deployment to Azure Functions.
- **Error isolation** - Failed API calls and download errors are caught per-activity and logged. Individual media failures do not crash the pipeline; the artifact still completes with partial results.

## Architecture

```
POST /api/artifacts ──► polling_orchestrator
                            │
                            ├─ fetchProfile
                            ├─ fetchPosts
                            ├─ fetchReels
                            ├─ downloadMedia  ──► blobs/ (local files)
                            └─ updateStatus   ──► MongoDB
```

1. Fetches the Instagram profile info (display name, profile picture)
2. Fetches recent posts and reels
3. Downloads all media (images, videos, thumbnails) to a local `blobs/` directory
4. Stores metadata, content, and blob records in MongoDB
5. Sets the artifact status to `"success"` (or `"failed"` on error)

Pagination is supported - once the initial scrape completes, you can request additional pages of posts or reels via the same `POST /api/artifacts` endpoint.

## API Reference

See [docs/api.md](docs/api.md) for full API documentation with request/response examples.

| Method | Endpoint              | Description                              |
| ------ | --------------------- | ---------------------------------------- |
| `POST` | `/api/artifacts`      | Start a new scrape or request pagination |
| `GET`  | `/api/artifacts`      | List all artifacts                       |
| `GET`  | `/api/artifacts/{id}` | Get a single artifact by ID              |
| `GET`  | `/api/blob/{blob_id}` | Serve a downloaded media file            |
| `GET`  | `/api/health`         | Health check                             |

## Project Structure

```
├── function_app.py          # HTTP endpoints and response formatting
├── api_blueprint.py         # Durable orchestrators and activity functions
├── exceptions.py            # Custom exception classes
├── apis/
│   └── external_api.py      # SociaVault API client and response parsers
├── database/
│   └── db.py                # MongoDB persistence layer
├── models/
│   └── artifact.py          # Pydantic data models
├── tests/                   # Unit tests (pytest + mongomock)
├── Dockerfile               # Container image for Azure deployment
├── host.json                # Azure Functions host configuration
├── requirements.txt         # Production dependencies
└── requirements-dev.txt     # Dev/test dependencies
```

## Prerequisites

- [Python 3.10–3.13](https://www.python.org/downloads/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Azure Functions Core Tools v4](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- A [SociaVault](https://sociavault.com/) API key

## Local Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/driedsoba/instagram-scrapper.git
cd instagram-scrapper
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

For development (includes pytest and mongomock):

```bash
pip install -r requirements-dev.txt
```

### 3. Create `local.settings.json`

This file is gitignored. Create it in the project root:

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsFeatureFlags": "EnableWorkerIndexing",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "SOCIAVAULT_API_KEY": "<your_sociavault_api_key>",
    "MONGODB_CONNECTION_STRING": "mongodb://localhost:27017"
  }
}
```

### 4. Start MongoDB and Azurite

Azure Durable Functions requires blob storage for orchestration state. Locally we use [Azurite](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite) as the storage emulator.

```bash
docker run -d --name mongodb -p 27017:27017 mongo:7
docker run -d --name azurite -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite
```

### 5. Start the function app

```bash
# macOS / Linux
func start

# Windows (PowerShell)
$env:languageWorkers__python__defaultExecutablePath = "$PWD\.venv\Scripts\python.exe"
func start
```

You should see all 5 HTTP routes loaded:

```
Functions:

        get_artifact:     [GET]  http://localhost:7071/api/artifacts/{artifact_id}
        get_artifacts:    [GET]  http://localhost:7071/api/artifacts
        get_blob:         [GET]  http://localhost:7071/api/blob/{blob_id}
        healthcheck:      [GET]  http://localhost:7071/api/health
        trigger_download: [POST] http://localhost:7071/api/artifacts
```

### 6. Try it out

```bash
# Health check
curl http://localhost:7071/api/health

# Start a new scrape
curl -X POST http://localhost:7071/api/artifacts \
  -H "Content-Type: application/json" \
  -d '{"case_id": "test-001", "identifier": "mothershipsg", "description": "Test scrape"}'

# Poll for status (replace <artifact_id> with the returned ID)
curl http://localhost:7071/api/artifacts/<artifact_id>

# List all artifacts
curl http://localhost:7071/api/artifacts

# Serve a downloaded media file (replace <blob_id> with a blob ID from contents)
curl http://localhost:7071/api/blob/<blob_id> --output media_file
```

## Running Tests

```bash
pytest
```

Tests use [mongomock](https://github.com/mongomock/mongomock) to mock MongoDB - no running database required.

## CI Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every PR to `main`:

1. **Lint** - [Ruff](https://docs.astral.sh/ruff/) check and format verification
2. **Test** - pytest suite
3. **Security** - [Bandit](https://bandit.readthedocs.io/) static analysis

## License

[MIT](LICENSE)
