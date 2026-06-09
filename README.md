# Moonshot Proxy Service

Tiny FastAPI service that exposes a single proxy endpoint, validates an operation-specific payload, routes the request
through a provider adapter, and returns a normalized response.

## Requirements

- Python 3.10+
- Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Service endpoint:

- `POST /proxy/execute`

FastAPI docs routes are disabled so the app exposes only the required proxy endpoint.
