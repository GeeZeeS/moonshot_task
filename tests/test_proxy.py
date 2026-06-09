import unittest

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import app.main as main
from app.core.errors import UpstreamServiceError
from app.providers.base import SportsProvider
from app.proxy.utils.decision_mapper import DecisionMapper


class FakeProvider(SportsProvider):
    name = "fake"
    base_url = "https://fake.example"

    async def list_leagues(self, payload: dict):
        return {
            "provider": self.name,
            "count": 1,
            "leagues": [
                {
                    "leagueId": 1,
                    "leagueShortcut": "bl1",
                    "leagueName": "Bundesliga",
                    "sport": {
                        "sportId": 1,
                        "sportName": "Fussball",
                    },
                }
            ],
        }

    async def get_league_matches(self, payload: dict):
        return {
            "provider": self.name,
            "leagueId": payload["leagueId"],
            "season": payload.get("season"),
            "count": 0,
            "matches": [],
        }

    async def get_league_standings(self, payload: dict):
        return {
            "provider": self.name,
            "leagueId": payload["leagueId"],
            "count": 1,
            "standings": [
                {
                    "team": {
                        "teamId": 16,
                        "teamName": "Test FC",
                        "shortName": "TFC",
                        "teamIconUrl": None,
                    },
                    "matches": 10,
                    "won": 7,
                    "draw": 2,
                    "lost": 1,
                    "goals": 20,
                    "opponentGoals": 8,
                    "goalDiff": 12,
                    "points": 23,
                }
            ],
        }

    async def get_matches_between_teams(self, payload: dict):
        return {
            "provider": self.name,
            "teamId1": payload["teamId1"],
            "teamId2": payload["teamId2"],
            "count": 0,
            "matches": [],
        }

    async def get_team(self, payload: dict):
        return {
            "provider": self.name,
            "team": {
                "teamId": payload["teamId"],
                "teamName": "Test FC",
                "shortName": "TFC",
                "teamIconUrl": None,
            },
        }

    def preview_target_url(self, operation_type: str, payload: dict[str, object]) -> str:
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

    def test_successful_proxy_request(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={"operationType": "GetTeam", "payload": {"teamId": 16}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "fake")
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

    def test_get_league_allows_league_id_without_season(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={
                "operationType": "GetLeague",
                "payload": {"leagueId": "bl1"},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["leagueId"], "bl1")
        self.assertIsNone(response.json()["season"])

    def test_get_league_season_allows_league_id_with_season(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={
                "operationType": "GetLeagueSeason",
                "payload": {"leagueId": "bl1", "season": 2024},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["leagueId"], "bl1")
        self.assertEqual(response.json()["season"], 2024)

    def test_get_league_matches_allows_string_league_id(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={
                "operationType": "GetLeagueMatches",
                "payload": {"leagueId": "wm26"},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["leagueId"], "wm26")
        self.assertIsNone(response.json()["season"])

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
        self.assertEqual(response.json()["count"], 1)

    def test_get_matches_between_teams_returns_matches(self) -> None:
        response = self.client.post(
            "/proxy/execute",
            json={
                "operationType": "GetMatchesBetweenTeams",
                "payload": {"teamId1": 16, "teamId2": 17},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["teamId1"], 16)
        self.assertEqual(response.json()["teamId2"], 17)

    def test_get_team_404_from_upstream_returns_not_implemented(self) -> None:
        original_mapper = main.app.state.decision_mapper
        main.app.state.decision_mapper = DecisionMapper(UnsupportedProvider())
        try:
            response = self.client.post(
                "/proxy/execute",
                json={"operationType": "GetTeam", "payload": {"teamId": 16}},
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
                "payload": {"teamId": 16},
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
