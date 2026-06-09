from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SportsProvider(ABC):
    name: str
    base_url: str

    @abstractmethod
    async def list_leagues(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_league(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_league_matches(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_league_standings(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_matches_between_teams(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_team(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def preview_target_url(self, operation_type: str, payload: dict[str, Any]) -> str:
        raise NotImplementedError
