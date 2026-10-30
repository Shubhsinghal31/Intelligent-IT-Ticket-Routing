"""
Smoke test — confirms the integration test infrastructure itself works
before anything else is built on top of it: real app, real Postgres
connection (via the transactional test session), real HTTP round-trip.
"""


class TestHealthEndpoint:
    def test_health_check_returns_ok(self, client):
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database_connected"] is True

    def test_health_check_includes_request_id_header(self, client):
        response = client.get("/api/v1/health")

        assert "X-Request-ID" in response.headers
