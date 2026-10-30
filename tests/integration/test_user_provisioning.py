"""
Admin-side user provisioning (POST /users) and department listing
(GET /departments), end to end against a real Postgres.

These two endpoints exist for the same reason: before them, the only way
to get an engineer or admin account was a database seed file — there was
no way for an admin to create one through the app, which meant the
"assign ticket to an engineer" picker had nobody to show unless you
hand-seeded a row. POST /users closes that gap; GET /departments backs
the department dropdown on the "Add User" form that calls it.
"""

from tests.integration.conftest import auth_headers, create_active_user, login, register


def _create_user(client, token: str, **overrides) -> dict:
    payload = {
        "email": "new.engineer@example.com",
        "username": "new_engineer",
        "password": "SecurePass123!",
        "full_name": "New Engineer",
        "role": "engineer",
    }
    payload.update(overrides)
    return client.post("/api/v1/users", headers=auth_headers(token), json=payload)


# =====================================================
# POST /users — RBAC
# =====================================================


class TestCreateUserRbac:
    def test_admin_can_create_engineer(self, client, db_session):
        create_active_user(db_session, "admin", "admin.provision@example.com", "admin_provision")
        db_session.commit()
        admin_token = login(client, "admin.provision@example.com")

        response = _create_user(client, admin_token)

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["role"] == "engineer"
        assert body["email"] == "new.engineer@example.com"
        assert body["is_active"] is True

    def test_admin_can_create_admin_account(self, client, db_session):
        create_active_user(db_session, "admin", "admin.provision2@example.com", "admin_provision2")
        db_session.commit()
        admin_token = login(client, "admin.provision2@example.com")

        response = _create_user(
            client,
            admin_token,
            email="second.admin@example.com",
            username="second_admin",
            role="admin",
        )

        assert response.status_code == 201, response.text
        assert response.json()["role"] == "admin"

    def test_employee_forbidden(self, client, db_session):
        register(client, "plain.employee@example.com", "plain_employee", "Plain Employee")
        employee_token = login(client, "plain.employee@example.com")

        response = _create_user(client, employee_token)

        assert response.status_code == 403

    def test_engineer_forbidden(self, client, db_session):
        create_active_user(db_session, "engineer", "eng.provision@example.com", "eng_provision")
        db_session.commit()
        engineer_token = login(client, "eng.provision@example.com")

        response = _create_user(client, engineer_token)

        assert response.status_code == 403

    def test_unauthenticated_request_returns_401(self, client):
        response = client.post(
            "/api/v1/users",
            json={
                "email": "no.auth@example.com",
                "username": "no_auth",
                "password": "SecurePass123!",
                "full_name": "No Auth",
                "role": "engineer",
            },
        )

        assert response.status_code == 401


# =====================================================
# POST /users — validation / business rules
# =====================================================


class TestCreateUserValidation:
    def test_duplicate_email_returns_409(self, client, db_session):
        create_active_user(db_session, "admin", "admin.dupe@example.com", "admin_dupe")
        db_session.commit()
        admin_token = login(client, "admin.dupe@example.com")

        first = _create_user(client, admin_token)
        assert first.status_code == 201

        second = _create_user(client, admin_token, username="a_different_username")
        assert second.status_code == 409
        assert second.json()["error_code"] == "CONFLICT"

    def test_unknown_role_returns_404(self, client, db_session):
        create_active_user(db_session, "admin", "admin.badrole@example.com", "admin_badrole")
        db_session.commit()
        admin_token = login(client, "admin.badrole@example.com")

        response = _create_user(client, admin_token, role="not_a_real_role")

        assert response.status_code == 404

    def test_unknown_department_returns_404(self, client, db_session):
        create_active_user(db_session, "admin", "admin.baddept@example.com", "admin_baddept")
        db_session.commit()
        admin_token = login(client, "admin.baddept@example.com")

        response = _create_user(client, admin_token, department_id=999999)

        assert response.status_code == 404

    def test_valid_department_id_is_persisted(self, client, db_session):
        from backend.models.department import Department

        create_active_user(db_session, "admin", "admin.gooddept@example.com", "admin_gooddept")
        department = db_session.query(Department).filter(Department.name == "IT Support").one()
        db_session.commit()
        admin_token = login(client, "admin.gooddept@example.com")

        response = _create_user(client, admin_token, department_id=department.id)

        assert response.status_code == 201, response.text
        assert response.json()["department"] == "IT Support"


# =====================================================
# GET /departments — RBAC
# =====================================================


class TestListDepartments:
    def test_admin_can_list_departments(self, client, db_session):
        create_active_user(db_session, "admin", "admin.deptlist@example.com", "admin_deptlist")
        db_session.commit()
        admin_token = login(client, "admin.deptlist@example.com")

        response = client.get("/api/v1/departments", headers=auth_headers(admin_token))

        assert response.status_code == 200
        names = [d["name"] for d in response.json()]
        assert "IT Support" in names
        assert "Network" in names

    def test_engineer_can_list_departments(self, client, db_session):
        create_active_user(db_session, "engineer", "eng.deptlist@example.com", "eng_deptlist")
        db_session.commit()
        engineer_token = login(client, "eng.deptlist@example.com")

        response = client.get("/api/v1/departments", headers=auth_headers(engineer_token))

        assert response.status_code == 200

    def test_employee_forbidden(self, client, db_session):
        register(client, "emp.deptlist@example.com", "emp_deptlist", "Emp Deptlist")
        employee_token = login(client, "emp.deptlist@example.com")

        response = client.get("/api/v1/departments", headers=auth_headers(employee_token))

        assert response.status_code == 403
