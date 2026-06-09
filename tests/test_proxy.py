import unittest

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import app.main as main
from app.core.errors import UpstreamServiceError
from app.providers.base import SportsProvider
from app.proxy.utils.decision_mapper import DecisionMapper
from tests.fixture_loader import load_fixture


class FakeProvider(SportsProvider):
    name = "fake"
    base_url = "https://fake.example"

    async def list_leagues(self, payload: dict):
        leagues = load_fixture("openliga", "list_leagues.json")
        return {
            "provider": self.name,
            "count": len(leagues),
            "leagues": leagues,
        }

    async def get_league(self, payload: dict):
        matches = load_fixture("openliga", "get_league_wm26.json")
        return {
            "provider": self.name,
            "leagueId": payload["leagueId"],
            "count": len(matches),
            "matches": matches,
        }

    async def get_league_matches(self, payload: dict):
        matches = load_fixture("openliga", "get_league_season_wm26_2026.json")
        return {
            "provider": self.name,
            "leagueId": payload["leagueId"],
            "season": payload.get("season"),
            "count": len(matches),
            "matches": matches,
        }

    async def get_league_standings(self, payload: dict):
        standings = load_fixture("openliga", "get_league_standings_bl1.json")
        return {
            "provider": self.name,
            "leagueId": payload["leagueId"],
            "count": len(standings),
            "standings": standings,
        }

    async def get_matches_between_teams(self, payload: dict):
        matches = load_fixture("openliga", "get_matches_between_teams_6447_2299.json")
        return {
            "provider": self.name,
            "teamId1": payload["teamId1"],
            "teamId2": payload["teamId2"],
            "count": len(matches),
            "matches": matches,
        }

    async def get_team(self, payload: dict):
        team = load_fixture("openliga", "get_team_6447.json")
        return {
            "provider": self.name,
            "team": team,
        }

    def preview_target_url(
        self, operation_type: str, payload: dict[str, object]
    ) -> str:
        return f"{self.base_url}/{operation_type}"


class UnsupportedProvider(FakeProvider):
    async def get_league_standings(self, payload: dict):
        raise UpstreamServiceError("not found", status_code=404)

    async def get_team(self, payload: dict):
        raise UpstreamServiceError("not found", status_code=404)


class ProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        @main.app.get("/test-cookies")
        async def test_cookies():
            response = JSONResponse({"ok": True})
            response.set_cookie("first", "1")
            response.set_cookie("second", "2")
            return response

        main.decision_mapper = DecisionMapper(FakeProvider())
        main.app.state.decision_mapper = main.decision_mapper
        cls.client = TestClient(main.app)
        cls.list_leagues_fixture = load_fixture("openliga", "list_leagues.json")
        cls.get_league_fixture = load_fixture("openliga", "get_league_wm26.json")
        cls.get_league_season_fixture = load_fixture(
            "openliga", "get_league_season_wm26_2026.json"
        )
        cls.get_team_fixture = load_fixture("openliga", "get_team_6447.json")
        cls.get_matches_between_teams_fixture = load_fixture(
            "openliga", "get_matches_between_teams_6447_2299.json"
        )
        cls.get_league_standings_fixture = load_fixture(
            "openliga", "get_league_standings_bl1.json"
        )

    def test_successful_proxy_request(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={"operationType": "GetTeam", "payload": {"teamId": 6447}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "fake")
        self.assertEqual(response.json()["team"]["teamId"], 6447)
        self.assertIn("x-request-id", response.headers)

    def test_unknown_operation_returns_400(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={"operationType": "Nope", "payload": {}},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "UNKNOWN_OPERATION")

    def test_validation_error_returns_400(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={"operationType": "GetTeam", "payload": {}},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "PAYLOAD_VALIDATION_ERROR")

    def test_get_all_leagues_returns_leagues(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={"operationType": "GetAllLeagues", "payload": {}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], len(self.list_leagues_fixture))
        self.assertEqual(
            response.json()["leagues"][0]["leagueShortcut"],
            self.list_leagues_fixture[0]["leagueShortcut"],
        )

    def test_get_league_allows_league_id_without_season(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={
                "operationType": "GetLeague",
                "payload": {"leagueId": "wm26"},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["leagueId"], "wm26")
        self.assertEqual(response.json()["count"], len(self.get_league_fixture))
        self.assertEqual(
            response.json()["matches"][0]["leagueShortcut"],
            self.get_league_fixture[0]["leagueShortcut"],
        )

    def test_get_league_season_allows_league_id_with_season(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={
                "operationType": "GetLeagueSeason",
                "payload": {"leagueId": "wm26", "season": 2026},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["leagueId"], "wm26")
        self.assertEqual(response.json()["season"], 2026)
        self.assertEqual(response.json()["count"], len(self.get_league_season_fixture))

    def test_get_league_season_requires_season(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={
                "operationType": "GetLeagueSeason",
                "payload": {"leagueId": "wm26"},
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "PAYLOAD_VALIDATION_ERROR")

    def test_get_league_standings_returns_standings(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={
                "operationType": "GetLeagueStandings",
                "payload": {"leagueId": "bl1"},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["leagueId"], "bl1")
        self.assertEqual(
            response.json()["count"], len(self.get_league_standings_fixture)
        )
        self.assertEqual(
            response.json()["standings"][0]["team"]["teamId"],
            self.get_league_standings_fixture[0]["team"]["teamId"],
        )

    def test_get_matches_between_teams_returns_matches(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={
                "operationType": "GetMatchesBetweenTeams",
                "payload": {"teamId1": 6447, "teamId2": 2299},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["teamId1"], 6447)
        self.assertEqual(response.json()["teamId2"], 2299)
        self.assertEqual(
            response.json()["count"], len(self.get_matches_between_teams_fixture)
        )

    def test_get_team_404_from_upstream_returns_not_implemented(self) -> None:
        original_mapper = main.app.state.decision_mapper
        main.app.state.decision_mapper = DecisionMapper(UnsupportedProvider())
        try:
            response = self.client.post(
                "/proxy/execute",
                json={"operationType": "GetTeam", "payload": {"teamId": 6447}},
            )
        finally:
            main.app.state.decision_mapper = original_mapper

        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.json()["code"], "OPERATION_NOT_IMPLEMENTED")

    def test_get_league_standings_404_from_upstream_returns_not_implemented(
        self,
    ) -> None:
        original_mapper = main.app.state.decision_mapper
        main.app.state.decision_mapper = DecisionMapper(UnsupportedProvider())
        try:
            response = self.client.post(
                "/proxy/execute",
                json={
                    "operationType": "GetLeagueStandings",
                    "payload": {"leagueId": "bl1"},
                },
            )
        finally:
            main.app.state.decision_mapper = original_mapper

        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.json()["code"], "OPERATION_NOT_IMPLEMENTED")

    def test_request_id_from_body_is_reused_in_response_header(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={
                "operationType": "GetTeam",
                "payload": {"teamId": 6447},
                "requestId": "body-request-id",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-request-id"], "body-request-id")

    def test_multiple_set_cookie_headers_are_preserved(self) -> None:
        response = self.client.get("/test-cookies")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.headers.get_list("set-cookie")), 2)


if __name__ == "__main__":
    unittest.main()
