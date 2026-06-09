from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ValidationError

from app.core.errors import ProxyError, UpstreamServiceError
from app.core.logging import log_event
from app.providers.base import SportsProvider
from app.providers.openliga_schemas import (
    GetLeagueMatchesPayload,
    GetLeaguePayload,
    GetLeagueStandingsPayload,
    GetMatchesBetweenTeamsPayload,
    GetTeamPayload,
    ListLeaguesPayload,
)

ProviderMethod = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class OperationConfig:
    payload_model: type[BaseModel]
    provider_method_name: str


OPERATIONS: dict[str, OperationConfig] = {
    "GetAllLeagues": OperationConfig(ListLeaguesPayload, "list_leagues"),
    "GetLeague": OperationConfig(GetLeaguePayload, "get_league"),
    "GetLeagueSeason": OperationConfig(GetLeagueMatchesPayload, "get_league_matches"),
    "GetTeam": OperationConfig(GetTeamPayload, "get_team"),
    "GetLeagueStandings": OperationConfig(
        GetLeagueStandingsPayload, "get_league_standings"
    ),
    "GetMatchesBetweenTeams": OperationConfig(
        GetMatchesBetweenTeamsPayload, "get_matches_between_teams"
    ),
}

NOT_IMPLEMENTED_ON_UPSTREAM = frozenset({"GetTeam", "GetLeagueStandings"})


class DecisionMapper:
    def __init__(self, provider: SportsProvider):
        self.provider = provider

    async def execute(
        self,
        request_id: str,
        operation_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        operation = OPERATIONS.get(operation_type)
        if operation is None:
            log_event(
                "audit.validation",
                requestId=request_id,
                operationType=operation_type,
                validationOutcome="fail",
                reasons=["Unknown operationType"],
            )
            raise ProxyError(
                message="Unknown operationType",
                code="UNKNOWN_OPERATION",
                status_code=400,
                details=[f"Unsupported operationType '{operation_type}'"],
            )

        try:
            validated_payload = operation.payload_model.model_validate(payload)
        except ValidationError as exc:
            details = [err["msg"] for err in exc.errors()]
            log_event(
                "audit.validation",
                requestId=request_id,
                operationType=operation_type,
                validationOutcome="fail",
                reasons=details,
            )
            raise ProxyError(
                message="Payload validation failed",
                code="PAYLOAD_VALIDATION_ERROR",
                status_code=400,
                details=details,
            ) from exc

        provider_method: ProviderMethod = getattr(
            self.provider, operation.provider_method_name
        )
        target_url = self.provider.preview_target_url(
            operation_type,
            validated_payload.model_dump(exclude_none=True),
        )
        log_event(
            "audit.validation",
            requestId=request_id,
            operationType=operation_type,
            validationOutcome="pass",
            reasons=[],
        )
        log_event(
            "audit.selection",
            requestId=request_id,
            operationType=operation_type,
            provider=self.provider.name,
            targetUrl=target_url,
        )

        started_at = time.perf_counter()
        try:
            response = await provider_method(
                validated_payload.model_dump(exclude_none=True)
            )
        except UpstreamServiceError as exc:
            latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                "audit.upstream",
                requestId=request_id,
                operationType=operation_type,
                provider=self.provider.name,
                targetUrl=target_url,
                upstreamStatusCode=exc.status_code,
                latencyMs=latency_ms,
                finalOutcome="error",
            )
            if exc.status_code == 404 and operation_type in NOT_IMPLEMENTED_ON_UPSTREAM:
                raise ProxyError(
                    message="Operation not implemented by upstream provider",
                    code="OPERATION_NOT_IMPLEMENTED",
                    status_code=501,
                    details=[
                        (
                            f"Operation '{operation_type}' is not supported by "
                            f"provider '{self.provider.name}'"
                        )
                    ],
                ) from exc
            raise ProxyError(
                message="Upstream API failed",
                code="UPSTREAM_API_FAILED",
                status_code=502,
                details=[],
            ) from exc

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_event(
            "audit.upstream",
            requestId=request_id,
            operationType=operation_type,
            provider=self.provider.name,
            targetUrl=target_url,
            upstreamStatusCode=200,
            latencyMs=latency_ms,
            finalOutcome="success",
        )

        return {
            "requestId": request_id,
            "operationType": operation_type,
            **response,
        }
