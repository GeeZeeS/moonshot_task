from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

OperationType = Literal["ListLeagues", "GetLeagueMatches", "GetTeam", "GetMatch"]


class ProxyRequest(BaseModel):
    operationType: str
    payload: dict[str, Any] = Field(default_factory=dict)
    requestId: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    code: str
    requestId: str
    details: list[str] = Field(default_factory=list)


class ListLeaguesPayload(BaseModel):
    season: Optional[int] = Field(default=None, ge=1900, le=2100)


class GetLeagueMatchesPayload(BaseModel):
    leagueShortcut: str = Field(min_length=1)
    season: int = Field(ge=1900, le=2100)
    groupOrderId: Optional[int] = Field(default=None, ge=1)


class GetTeamPayload(BaseModel):
    teamId: int = Field(gt=0)


class GetMatchPayload(BaseModel):
    matchId: int = Field(gt=0)
