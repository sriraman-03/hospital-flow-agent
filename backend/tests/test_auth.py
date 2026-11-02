from tests.conftest import PASSWORD


def test_login_success_and_me(client, auth):
    r = client.get("/api/v1/auth/me", headers=auth())
    assert r.status_code == 200
    assert r.json()["role"] == "administrator"
    assert "users:manage" in r.json()["permissions"]


def test_login_wrong_password_is_generic_401(client, users):
    r = client.post("/api/v1/auth/login", json={"email": "administrator@test.local", "password": "nope-nope-nope"})
    assert r.status_code == 401
    r2 = client.post("/api/v1/auth/login", json={"email": "ghost@test.local", "password": PASSWORD})
    assert r2.status_code == 401
    assert r.json()["error"]["message"] == r2.json()["error"]["message"]  # no account enumeration


def test_protected_routes_require_token(client):
    assert client.get("/api/v1/patients").status_code == 401
    assert client.get("/api/v1/patients", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_viewer_cannot_write(client, auth):
    r = client.post("/api/v1/patients", headers=auth("viewer"),
                    json={"first_name": "A", "last_name": "B", "date_of_birth": "1990-01-01"})
    assert r.status_code == 403
    assert client.get("/api/v1/patients", headers=auth("viewer")).status_code == 200


def test_audit_logs_admin_only(client, auth):
    assert client.get("/api/v1/audit-logs", headers=auth("administrator")).status_code == 200
    for role in ("operations_staff", "department_staff", "viewer"):
        assert client.get("/api/v1/audit-logs", headers=auth(role)).status_code == 403


def test_user_admin_admin_only(client, auth):
    assert client.get("/api/v1/users", headers=auth("operations_staff")).status_code == 403
    assert client.get("/api/v1/users", headers=auth("administrator")).status_code == 200


def test_logout_revokes_token(client, auth):
    h = auth("viewer")
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 200
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401


def test_weak_password_rejected_on_user_create(client, auth):
    r = client.post("/api/v1/users", headers=auth(), json={"email": "x@test.local", "full_name": "X", "password": "short", "role": "viewer"})
    assert r.status_code == 422


def test_error_shape_has_no_stack_trace(client, auth):
    r = client.get("/api/v1/patients/99999", headers=auth())
    assert r.status_code == 404
    assert set(r.json()["error"]) == {"code", "message", "details"}


def test_health_and_ready(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/ready").status_code == 200
