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

## Request Format

All traffic goes through the same endpoint:

```bash
curl -X POST http://127.0.0.1:8000/proxy/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operationType": "GetAllLeagues",
    "requestId": "optional-client-request-id",
    "payload": {}
  }'
```

Top-level fields:

- `operationType`: required string, must exactly match one of the supported operations below
- `payload`: required object, validated per operation
- `requestId`: optional string; if omitted, the service generates one and also returns it in the `x-request-id` response
  header

## Supported Operations

### `GetAllLeagues`

Returns all leagues from the configured upstream provider.

Payload:

```json
{}
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/proxy/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operationType": "GetAllLeagues",
    "payload": {}
  }'
```

### `GetLeague`

Returns match data for a league.

Payload:

```json
{
  "leagueId": "bl2f"
}
```

Fields:

- `leagueId`: required string, for example `wm26`

Example:

```bash
curl -X POST http://127.0.0.1:8000/proxy/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operationType": "GetLeague",
    "payload": {
      "leagueId": "wm26"
    }
  }'
```

### `GetLeagueSeason`

Returns match data for a league in a specific season.

Payload:

```json
{
  "leagueId": "wm26",
  "season": 2026
}
```

Fields:

- `leagueId`: required string
- `season`: required integer between `1900` and `2100`

Example:

```bash
curl -X POST http://127.0.0.1:8000/proxy/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operationType": "GetLeagueSeason",
    "payload": {
      "leagueId": "wm26",
      "season": 2026
    }
  }'
```

### `GetLeagueStandings`

Returns standings for a league.

Payload:

```json
{
  "leagueId": "wm26"
}
```

Fields:

- `leagueId`: required string

Example:

```bash
curl -X POST http://127.0.0.1:8000/proxy/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operationType": "GetLeagueStandings",
    "payload": {
      "leagueId": "wm26"
    }
  }'
```

### `GetMatchesBetweenTeams`

Returns matches between two teams.

Payload:

```json
{
  "teamId1": 6447,
  "teamId2": 2299
}
```

Fields:

- `teamId1`: required integer
- `teamId2`: required integer

Example:

```bash
curl -X POST http://127.0.0.1:8000/proxy/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operationType": "GetMatchesBetweenTeams",
    "payload": {
      "teamId1": 6447,
      "teamId2": 2299
    }
  }'
```

### `GetTeam`

Returns team details.

Payload:

```json
{
  "teamId": 6447
}
```

Fields:

- `teamId`: required integer

Example:

```bash
curl -X POST http://127.0.0.1:8000/proxy/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operationType": "GetTeam",
    "payload": {
      "teamId": 6447
    }
  }'
```

## Response Shape

Successful responses always include:

- `requestId`
- `operationType`
- `provider`

The remaining fields depend on the operation, for example:

- `GetAllLeagues`: `count`, `leagues`
- `GetLeague`: `leagueId`, `count`, `matches`
- `GetLeagueSeason`: `leagueId`, `season`, `count`, `matches`
- `GetLeagueStandings`: `leagueId`, `count`, `standings`
- `GetMatchesBetweenTeams`: `teamId1`, `teamId2`, `count`, `matches`
- `GetTeam`: `team`

## Error Responses

Handled errors return this structure:

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

Expected error codes:

- `UNKNOWN_OPERATION`: unsupported `operationType`
- `PAYLOAD_VALIDATION_ERROR`: missing or invalid payload fields
- `OPERATION_NOT_IMPLEMENTED`: upstream does not support that operation
- `UPSTREAM_API_FAILED`: upstream request failed after retry handling
