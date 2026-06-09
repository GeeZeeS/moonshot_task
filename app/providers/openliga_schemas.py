from typing import Optional

from pydantic import BaseModel, Field


class SportSchema(BaseModel):
    sportId: int
    sportName: str


class LeagueSchema(BaseModel):
    leagueId: int
    leagueName: str
    leagueShortcut: str
    leagueSeason: str
    sport: SportSchema


class MatchGroupSchema(BaseModel):
    groupName: str
    groupOrderID: int
    groupID: int


class TeamSchema(BaseModel):
    teamId: int
    teamName: str
    shortName: str
    teamIconUrl: str
    teamGroupName: str | None = None


class LocationSchema(BaseModel):
    locationID: int
    locationCity: str
    locationStadium: str


class MatchSchema(BaseModel):
    matchID: int
    matchDateTime: str
    timeZoneID: str
    leagueId: int
    leagueName: str
    leagueSeason: int
    leagueShortcut: str
    matchDateTimeUTC: str
    group: MatchGroupSchema
    team1: TeamSchema
    team2: TeamSchema
    lastUpdateDateTime: str
    matchIsFinished: bool
    matchResults: list
    goals: list
    location: LocationSchema | None = None
    numberOfViewers: int | None = None


class ListLeaguesPayload(BaseModel):
    pass


class ListLeaguesResponse(BaseModel):
    provider: str
    count: int
    leagues: list[LeagueSchema]


class GetLeaguePayload(BaseModel):
    leagueId: str


class GetLeagueResponse(BaseModel):
    provider: str
    leagueId: str
    count: int
    matches: list[MatchSchema]


class GetLeagueMatchesPayload(BaseModel):
    leagueId: str
    season: int = Field(ge=1900, le=2100)


class GetLeagueMatchesResponse(BaseModel):
    provider: str
    leagueId: str
    season: int
    count: int
    matches: list[MatchSchema]


class GetTeamPayload(BaseModel):
    teamId: int


class GetTeamResponse(BaseModel):
    provider: str
    team: TeamSchema


class GetLeagueStandingsPayload(BaseModel):
    leagueId: str


class GetLeagueStandingsResponse(BaseModel):
    provider: str
    leagueId: str
    count: int
    standings: list


class GetMatchesBetweenTeamsPayload(BaseModel):
    teamId1: int
    teamId2: int


class GetMatchesBetweenTeamsResponse(BaseModel):
    provider: str
    teamId1: int | None
    teamId2: int | None
    count: int
    matches: list[MatchSchema]
