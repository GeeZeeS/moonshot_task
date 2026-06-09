from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import UpstreamServiceError
from app.providers.base import SportsProvider
from app.providers.rate_limiter import RateLimiter


class OpenLigaProvider(SportsProvider):
    name = "openliga"
    transient_status_codes = {429, 500, 502, 503, 504}

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

    async def list_leagues(self, payload: dict[str, Any]) -> dict[str, Any]:
        season = payload.get("season")
        path = f"/getavailableleagues/{season}" if season else "/getavailableleagues"
        leagues = await self._request_json(path)
        normalized = [
            {
                "leagueId": item.get("leagueId"),
                "leagueShortcut": item.get("leagueShortcut"),
                "leagueName": item.get("leagueName"),
                "sportName": (item.get("sport") or {}).get("sportName"),
            }
            for item in leagues
        ]
        return {"provider": self.name, "count": len(normalized), "leagues": normalized}

    async def get_league_matches(self, payload: dict[str, Any]) -> dict[str, Any]:
        league_shortcut = payload["leagueShortcut"]
        season = payload["season"]
        group_order_id = payload.get("groupOrderId")
        if group_order_id is None:
            path = f"/getmatchdata/{league_shortcut}/{season}"
        else:
            path = f"/getmatchdata/{league_shortcut}/{season}/{group_order_id}"

        matches = await self._request_json(path)
        normalized_matches = [self._normalize_match(match) for match in matches]
        return {
            "provider": self.name,
            "leagueShortcut": league_shortcut,
            "season": season,
            "groupOrderId": group_order_id,
            "count": len(normalized_matches),
            "matches": normalized_matches,
        }

    async def get_team(self, payload: dict[str, Any]) -> dict[str, Any]:
        team_id = payload["teamId"]
        team = await self._request_json(f"/getteam/{team_id}")
        normalized = {
            "teamId": team.get("teamId"),
            "teamName": team.get("teamName"),
            "shortName": team.get("shortName"),
            "teamIconUrl": team.get("teamIconUrl"),
        }
        return {"provider": self.name, "team": normalized}

    async def get_match(self, payload: dict[str, Any]) -> dict[str, Any]:
        match_id = payload["matchId"]
        match = await self._request_json(f"/getmatchdata/{match_id}")
        return {"provider": self.name, "match": self._normalize_match(match)}

    def preview_target_url(self, operation_type: str, payload: dict[str, Any]) -> str:
        if operation_type == "ListLeagues":
            season = payload.get("season")
            path = (
                f"/getavailableleagues/{season}" if season else "/getavailableleagues"
            )
        elif operation_type == "GetLeagueMatches":
            league_shortcut = payload["leagueShortcut"]
            season = payload["season"]
            group_order_id = payload.get("groupOrderId")
            if group_order_id is None:
                path = f"/getmatchdata/{league_shortcut}/{season}"
            else:
                path = f"/getmatchdata/{league_shortcut}/{season}/{group_order_id}"
        elif operation_type == "GetTeam":
            path = f"/getteam/{payload['teamId']}"
        elif operation_type == "GetMatch":
            path = f"/getmatchdata/{payload['matchId']}"
        else:
            path = ""
        return f"{self.base_url}{path}"

    async def _request_json(self, path: str) -> Any:
        last_error: UpstreamServiceError | None = None

        for attempt in range(1, self.retry_attempts + 1):
            try:
                return await self._perform_request(path)
            except UpstreamServiceError as exc:
                last_error = exc
                if (
                    exc.status_code not in self.transient_status_codes
                    or attempt == self.retry_attempts
                ):
                    raise
            except httpx.TimeoutException as exc:
                last_error = UpstreamServiceError("Upstream request timed out")
                if attempt == self.retry_attempts:
                    raise last_error from exc
            except httpx.HTTPError as exc:
                last_error = UpstreamServiceError("Upstream HTTP error")
                if attempt == self.retry_attempts:
                    raise last_error from exc

            delay = min(
                self.retry_base_delay_seconds * (2 ** (attempt - 1)),
                self.retry_max_delay_seconds,
            )
            delay += random.uniform(0, delay / 4 if delay else 0.1)
            await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error

    async def _perform_request(self, path: str) -> Any:
        await self.rate_limiter.acquire()
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout
        ) as client:
            response = await client.get(path)

        if response.status_code >= 400:
            raise UpstreamServiceError(
                message=f"OpenLiga returned status {response.status_code}",
                status_code=response.status_code,
            )
        return response.json()

    @staticmethod
    def _normalize_match(match: dict[str, Any]) -> dict[str, Any]:
        final_result = None
        for result in match.get("matchResults", []):
            if result.get("resultName") == "Endergebnis":
                final_result = result
                break
        if final_result is None and match.get("matchResults"):
            final_result = match["matchResults"][-1]

        return {
            "matchId": match.get("matchID"),
            "matchDateTimeUtc": match.get("matchDateTimeUTC"),
            "matchIsFinished": match.get("matchIsFinished"),
            "leagueId": match.get("leagueId"),
            "leagueName": match.get("leagueName"),
            "leagueSeason": match.get("leagueSeason"),
            "group": {
                "groupOrderId": (match.get("group") or {}).get("groupOrderID"),
                "groupName": (match.get("group") or {}).get("groupName"),
            },
            "team1": OpenLigaProvider._normalize_team(match.get("team1")),
            "team2": OpenLigaProvider._normalize_team(match.get("team2")),
            "score": {
                "team1": None
                if final_result is None
                else final_result.get("pointsTeam1"),
                "team2": None
                if final_result is None
                else final_result.get("pointsTeam2"),
            },
            "location": {
                "locationId": (match.get("location") or {}).get("locationID"),
                "locationCity": (match.get("location") or {}).get("locationCity"),
                "locationStadium": (match.get("location") or {}).get("locationStadium"),
            },
            "lastUpdateDateTime": match.get("lastUpdateDateTime"),
        }

    @staticmethod
    def _normalize_team(team: dict[str, Any] | None) -> dict[str, Any] | None:
        if team is None:
            return None
        return {
            "teamId": team.get("teamId"),
            "teamName": team.get("teamName"),
            "shortName": team.get("shortName"),
            "teamIconUrl": team.get("teamIconUrl"),
        }
