"""
End-to-end auth flow: register -> login -> access a protected route.

This is the kind of bug integration tests catch that mocked unit tests
structurally cannot: every layer (Pydantic validation, password
hashing, the roles foreign key, JWT encode/decode, the RBAC dependency)
has to actually agree with every other layer, not just with whatever a
given unit test's mocks assumed they'd return.
"""


class TestRegisterAndLogin:
    def test_register_creates_employee_by_default(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "new.hire@example.com",
                "username": "new_hire",
                "password": "SecurePass123!",
                "full_name": "New Hire",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "new.hire@example.com"
        assert body["role"] == "employee"

    def test_duplicate_email_is_rejected(self, client):
        payload = {
            "email": "dupe@example.com",
            "username": "dupe_one",
            "password": "SecurePass123!",
            "full_name": "Dupe One",
        }
        first = client.post("/api/v1/auth/register", json=payload)
        assert first.status_code == 201

        payload["username"] = "dupe_two"
        second = client.post("/api/v1/auth/register", json=payload)
        assert second.status_code == 409
        assert second.json()["error_code"] == "CONFLICT"

    def test_login_then_access_protected_route(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "login.flow@example.com",
                "username": "login_flow",
                "password": "SecurePass123!",
                "full_name": "Login Flow",
            },
        )

        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "login.flow@example.com", "password": "SecurePass123!"},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        assert "access_token" in tokens

        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "login.flow@example.com"

    def test_wrong_password_returns_401_with_request_id(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrong.pass@example.com",
                "username": "wrong_pass",
                "password": "SecurePass123!",
                "full_name": "Wrong Pass",
            },
        )

        response = client.post(
            "/api/v1/auth/login",
            data={"username": "wrong.pass@example.com", "password": "not-the-password"},
        )

        assert response.status_code == 401
        body = response.json()
        assert body["error_code"] == "UNAUTHORIZED"
        assert body["request_id"] is not None
        assert response.headers["X-Request-ID"] == body["request_id"]

    def test_protected_route_without_token_returns_401(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
