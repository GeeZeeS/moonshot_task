import unittest

from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

import app.main as main
from app.proxy.utils.decision_mapper import DecisionMapper
from app.providers.base import SportsProvider


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
                    "sportName": "Fussball",
                }
            ],
        }

    async def get_league_matches(self, payload: dict):
        return {
            "provider": self.name,
            "leagueShortcut": payload["leagueShortcut"],
            "season": payload["season"],
            "groupOrderId": payload.get("groupOrderId"),
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

    async def get_match(self, payload: dict):
        return {"provider": self.name, "match": {"matchId": payload["matchId"]}}

    def preview_target_url(self, operation_type: str, payload: dict[str, object]) -> str:
        return f"{self.base_url}/{operation_type}"


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
