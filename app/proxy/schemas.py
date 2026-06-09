from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

OperationType = Literal[
    "GetAllLeagues",
    "GetLeague",
    "GetLeagueSeason",
    "GetLeagueStandings",
    "GetMatchesBetweenTeams",
    "GetTeam",
]


class ProxyRequest(BaseModel):
    operationType: str
    payload: dict[str, Any] = Field(default_factory=dict)
    requestId: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    code: str
    requestId: str
    details: list[str] = Field(default_factory=list)
