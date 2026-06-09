# Moonshot Proxy Service

Tiny FastAPI service that exposes a single proxy endpoint, validates an operation-specific payload, routes the request through a provider adapter, and returns a normalized response.

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

## Request Contract

Top-level request body:

```json
{
  "operationType": "ListLeagues",
  "requestId": "optional-client-request-id",
  "payload": {}
}
```

If `requestId` is omitted, the service generates one and also returns it in the response header `x-request-id`.

## Operation Schemas

### `ListLeagues`

Payload:

```json
{
  "season": 2025
}
```

Fields:

- `season` optional integer; if omitted, OpenLiga's default league list endpoint is used

Normalized response fields:

- `requestId`
- `operationType`
- `provider`
- `count`
- `leagues[]`
- `leagues[].leagueId`
- `leagues[].leagueShortcut`
- `leagues[].leagueName`
- `leagues[].sportName`

Example request:

```bash
curl -X POST http://127.0.0.1:8000/proxy/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operationType": "ListLeagues",
    "payload": {
      "season": 2025
    }
  }'
```

### `GetLeagueMatches`

Payload:

```json
{
  "leagueShortcut": "bl1",
  "season": 2025,
  "groupOrderId": 1
}
```

Fields:

- `leagueShortcut` required string, for example `bl1`
- `season` required integer
- `groupOrderId` optional integer for a specific matchday/group

Normalized response fields:

- `requestId`
- `operationType`
- `provider`
- `leagueShortcut`
- `season`
- `groupOrderId`
- `count`
- `matches[]`
- `matches[].matchId`
- `matches[].matchDateTimeUtc`
- `matches[].matchIsFinished`
- `matches[].leagueId`
- `matches[].leagueName`
- `matches[].leagueSeason`
- `matches[].group`
- `matches[].team1`
- `matches[].team2`
- `matches[].score`
- `matches[].location`
- `matches[].lastUpdateDateTime`

Example request:

```bash
curl -X POST http://127.0.0.1:8000/proxy/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operationType": "GetLeagueMatches",
    "payload": {
      "leagueShortcut": "bl1",
      "season": 2025,
      "groupOrderId": 1
    }
  }'
```

### `GetTeam`

Payload:

```json
{
  "teamId": 16
}
```

Fields:

- `teamId` required positive integer

Normalized response fields:

- `requestId`
- `operationType`
- `provider`
- `team`
- `team.teamId`
- `team.teamName`
- `team.shortName`
- `team.teamIconUrl`

Example request:

```bash
curl -X POST http://127.0.0.1:8000/proxy/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operationType": "GetTeam",
    "payload": {
      "teamId": 16
    }
  }'
```

### `GetMatch`

Payload:

```json
{
  "matchId": 12345
}
```

Fields:

- `matchId` required positive integer

Normalized response fields:

- `requestId`
- `operationType`
- `provider`
- `match`
- `match.matchId`
- `match.matchDateTimeUtc`
- `match.matchIsFinished`
- `match.leagueId`
- `match.leagueName`
- `match.leagueSeason`
- `match.group`
- `match.team1`
- `match.team2`
- `match.score`
- `match.location`
- `match.lastUpdateDateTime`

Example request:

```bash
curl -X POST http://127.0.0.1:8000/proxy/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operationType": "GetMatch",
    "payload": {
      "matchId": 12345
    }
  }'
```

## Decision Mapper

The decision mapper lives in `app/proxy/utils/decision_mapper.py`.

- It looks up `operationType` in a fixed mapping.
- Each operation maps to a Pydantic payload schema and a provider method name.
- The mapper validates the payload, logs the validation result, logs the selected provider and target URL, then calls the provider method.
- Unknown operations and validation failures return `400`.
- Upstream failures after retries return `502` with a small structured error object.

## Adapter Pattern

Provider interface:

- `app/providers/base.py` defines the `SportsProvider` contract.
- `app/providers/openliga.py` implements `OpenLigaProvider`.

Swap behavior:

- The HTTP endpoint and decision mapper only depend on the provider interface.
- OpenLiga-specific URLs and path construction stay inside `OpenLigaProvider`.
- Provider selection is configured through `SPORTS_PROVIDER` in `app/base/config.py`.

## Rate Limiting And Backoff

Configuration is read from environment variables:

- `SPORTS_PROVIDER` default `openliga`
- `OPENLIGA_BASE_URL` default `https://api.openligadb.de`
- `UPSTREAM_TIMEOUT_SECONDS` default `10`
- `UPSTREAM_RATE_LIMIT_COUNT` default `5`
- `UPSTREAM_RATE_LIMIT_WINDOW_SECONDS` default `1`
- `UPSTREAM_RETRY_ATTEMPTS` default `3`
- `UPSTREAM_RETRY_BASE_DELAY_SECONDS` default `0.5`
- `UPSTREAM_RETRY_MAX_DELAY_SECONDS` default `4`
- `LOG_BODY_PREVIEW_CHARS` default `300`

Behavior:

- Rate limiting is enforced per process before each upstream request.
- Retries use exponential backoff with jitter.
- Retries are triggered for `429`, `500`, `502`, `503`, `504`, timeouts, and transport-level HTTP errors.

## Logging

Structured JSON logs are written to stdout.

What gets logged:

- Inbound request metadata via middleware
- Outbound response metadata via middleware
- Validation outcome
- Selected provider and target URL
- Upstream status and latency
- Final outcome

Sensitive headers are redacted and logged bodies are truncated.

Sample log:

```json
{
  "event": "audit.upstream",
  "timestamp": "2026-06-08T09:00:00+00:00",
  "requestId": "8bfc4bf1-16fd-40e0-9b7d-83c40fbd7f85",
  "operationType": "GetLeagueMatches",
  "provider": "openliga",
  "targetUrl": "https://api.openligadb.de/getmatchdata/bl1/2025/1",
  "upstreamStatusCode": 200,
  "latencyMs": 182.44,
  "finalOutcome": "success"
}
```

## Error Shape

Every handled error returns this structure:

```json
{
  "error": "Payload validation failed",
  "code": "PAYLOAD_VALIDATION_ERROR",
  "requestId": "generated-or-forwarded-request-id",
  "details": [
    "Field required"
  ]
}
```

Error cases:

- Unknown `operationType` -> `400`
- Payload validation failure -> `400`
- Upstream failure after retries -> `502`
