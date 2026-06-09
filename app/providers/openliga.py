from __future__ import annotations

import asyncio
import json
import random
from typing import Any

from httpx import AsyncClient, HTTPError, TimeoutException

from app.core.config import settings
from app.core.errors import UpstreamServiceError
from app.providers.base import SportsProvider
from app.providers.openliga_schemas import (
    GetLeagueMatchesResponse,
    GetLeagueResponse,
    GetLeagueStandingsResponse,
    GetMatchesBetweenTeamsResponse,
    GetTeamResponse,
    LeagueSchema,
    ListLeaguesResponse,
    MatchSchema,
    TeamSchema,
)
from app.providers.rate_limiter import RateLimiter


class OpenLigaClient:
    transient_status_codes = frozenset({429, 500, 502, 503, 504})

    def __init__(self):
        self.base_url = settings.openliga_base_url.rstrip("/")
        self.timeout = settings.upstream_timeout_seconds
        self.retry_attempts = settings.upstream_retry_attempts
        self.retry_base_delay_seconds = settings.upstream_retry_base_delay_seconds
        self.retry_max_delay_seconds = settings.upstream_retry_max_delay_seconds
        self.rate_limiter = RateLimiter(
            limit=settings.upstream_rate_limit_count,
            window_seconds=settings.upstream_rate_limit_window_seconds,
        )

    def preview_target_url(self, operation_type: str, payload: dict[str, Any]) -> str:
        return f"{self.base_url}{self._build_path(operation_type, payload)}"

    @classmethod
    def _build_path(cls, operation_type: str, payload: dict[str, Any]) -> str:
        match operation_type:
            case "GetAllLeagues":
                return "/getavailableleagues"
            case "GetLeague":
                return f"/getmatchdata/{payload['leagueId']}"
            case "GetLeagueSeason":
                return f"/getmatchdata/{payload['leagueId']}/{payload['season']}"
            case "GetTeam":
                return f"/getteam/{payload['teamId']}"
            case "GetLeagueStandings":
                return f"/getbltable/{payload['leagueId']}"
            case "GetMatchesBetweenTeams":
                return f"/getmatchdata/{payload['teamId1']}/{payload['teamId2']}"
            case _:
                raise ValueError(f"Unsupported operation type: {operation_type}")

    async def request(self, operation_type: str, payload: dict[str, Any]) -> Any:
        last_error = None

        for attempt in range(1, self.retry_attempts + 1):
            try:
                return await self._perform_request(
                    self._build_path(operation_type, payload)
                )
            except (UpstreamServiceError, TimeoutException, HTTPError) as exc:
                last_error = self._to_upstream_error(exc)
                if not self._should_retry(last_error, attempt):
                    if isinstance(exc, UpstreamServiceError):
                        raise
                    raise last_error from exc

            await asyncio.sleep(self._backoff_delay(attempt))

        assert last_error is not None
        raise last_error

    async def _perform_request(self, path: str) -> Any:
        await self.rate_limiter.acquire()
        async with AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.get(path)

        if response.status_code >= 400:
            raise UpstreamServiceError(
                message=f"{path=} returned status {response.status_code}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            body_preview = response.text[:200]
            raise UpstreamServiceError(
                message=(f"{path=} returned non-JSON response: {body_preview!r}")
            ) from exc

    def _should_retry(self, error: UpstreamServiceError, attempt: int) -> bool:
        if attempt >= self.retry_attempts:
            return False
        return (
            error.status_code in self.transient_status_codes
            or error.status_code is None
        )

    @staticmethod
    def _to_upstream_error(
        error: UpstreamServiceError | TimeoutException | HTTPError,
    ) -> UpstreamServiceError:
        if isinstance(error, UpstreamServiceError):
            return error
        if isinstance(error, TimeoutException):
            return UpstreamServiceError("Upstream request timed out")
        return UpstreamServiceError("Upstream HTTP error")

    def _backoff_delay(self, attempt: int) -> float:
        delay = float(
            min(
                self.retry_base_delay_seconds * (2 ** (attempt - 1)),
                self.retry_max_delay_seconds,
            )
        )
        jitter = random.uniform(0, delay / 4 if delay else 0.1)
        return delay + jitter


class OpenLigaProvider(SportsProvider):
    name = "openliga"

    def __init__(self):
        self.client = OpenLigaClient()
        self.base_url = self.client.base_url

    async def list_leagues(self, payload: dict[str, Any]) -> ListLeaguesResponse:
        leagues = await self.client.request("GetAllLeagues", payload)
        return ListLeaguesResponse(
            provider=self.name,
            count=len(leagues),
            leagues=[LeagueSchema(**item) for item in leagues],
        ).model_dump()

    async def get_league(self, payload: dict[str, Any]):
        matches = await self.client.request("GetLeague", payload)
        return GetLeagueResponse(
            provider=self.name,
            leagueId=payload["leagueId"],
            count=len(matches),
            matches=[MatchSchema(**match) for match in (matches or [])],
        ).model_dump()

    async def get_league_matches(self, payload: dict[str, Any]):
        matches = await self.client.request("GetLeagueSeason", payload)
        return GetLeagueMatchesResponse(
            provider=self.name,
            leagueId=payload["leagueId"],
            season=payload["season"],
            count=len(matches),
            matches=[MatchSchema(**match) for match in (matches or [])],
        ).model_dump()

    async def get_matches_between_teams(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        matches = await self.client.request("GetMatchesBetweenTeams", payload)
        return GetMatchesBetweenTeamsResponse(
            provider=self.name,
            teamId1=payload["teamId1"],
            teamId2=payload["teamId2"],
            count=len(matches),
            matches=[MatchSchema(**match) for match in (matches or [])],
        ).model_dump()

    async def get_league_standings(self, payload: dict[str, Any]) -> dict[str, Any]:
        standings = await self.client.request("GetLeagueStandings", payload)
        return GetLeagueStandingsResponse(
            provider=self.name,
            leagueId=payload["leagueId"],
            count=len(standings),
            standings=[MatchSchema(**match) for match in (standings or [])],
        ).model_dump()

    async def get_team(self, payload: dict[str, Any]) -> dict[str, Any]:
        team = await self.client.request("GetTeam", payload)
        return GetTeamResponse(
            provider=self.name,
            team=TeamSchema(**team),
        ).model_dump()

    def preview_target_url(self, operation_type: str, payload: dict[str, Any]) -> str:
        return self.client.preview_target_url(operation_type, payload)
