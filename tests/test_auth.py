from tests.conftest import ADMIN_PASSWORD, Client


def test_pages_redirect_when_logged_out(client):
    assert client.get("/").status_code == 302
    assert client.get("/login").status_code == 200


def test_api_requires_login(client):
    r = client.get("/api/databases")
    assert r.status_code == 401
    assert "error" in r.get_json()


def test_login_success_and_me(client):
    r = client.login()
    assert r.status_code == 200
    assert r.get_json()["user"]["role"] == "admin"
    assert "password_hash" not in r.get_json()["user"]
    assert client.get("/api/auth/me").get_json()["user"]["username"] == "admin"


def test_login_failure_message_is_generic(client):
    r = client.login("admin", "wrong")
    assert r.status_code == 401
    r2 = client.login("nobody", "wrong")
    assert r.get_json()["error"] == r2.get_json()["error"]


def test_csrf_required(app):
    c = Client(app)
    c.login()
    bad = c.http.post("/api/databases/test", json={})
    assert bad.status_code == 403
    assert "CSRF" in bad.get_json()["error"]


def test_lockout(app):
    c = Client(app)
    for _ in range(5):
        assert c.login("admin", "bad").status_code == 401
    assert c.login("admin", ADMIN_PASSWORD).status_code == 429


def test_logout(admin):
    assert admin.post("/api/auth/logout").status_code == 200
    assert admin.get("/api/auth/me").status_code == 401


def test_roles(admin, operator):
    assert operator.get("/api/databases").status_code == 200
    assert operator.post("/api/databases", {}).status_code == 403
    assert operator.get("/api/logs").status_code == 403
    assert operator.get("/api/users").status_code == 403
    assert operator.get("/logs").status_code == 403
    assert admin.get("/api/logs").status_code == 200


def test_user_management_rules(admin):
    users = admin.get("/api/users").get_json()["items"]
    admin_id = users[0]["id"]
    assert admin.delete(f"/api/users/{admin_id}").status_code == 400
    assert admin.put(f"/api/users/{admin_id}", {"role": "operator"}).status_code == 400
    assert admin.post("/api/users", {"username": "x", "password": "Password1", "role": "admin"}).status_code == 400
    assert admin.post("/api/users", {"username": "weakuser", "password": "short", "role": "admin"}).status_code == 400
    assert admin.post("/api/users", {"username": "gooduser", "password": "Password1", "role": "admin"}).status_code == 201
    assert admin.post("/api/users", {"username": "gooduser", "password": "Password1", "role": "admin"}).status_code == 409


def test_change_password(app, admin):
    assert admin.post("/api/auth/change-password",
                      {"current_password": "nope", "new_password": "NewPass123"}).status_code == 401
    assert admin.post("/api/auth/change-password",
                      {"current_password": ADMIN_PASSWORD, "new_password": "NewPass123"}).status_code == 200
    fresh = Client(app)
    assert fresh.login(password=ADMIN_PASSWORD).status_code == 401
    assert fresh.login(password="NewPass123").status_code == 200


def test_deleted_user_loses_access(app, admin, operator):
    oper_id = [u for u in admin.get("/api/users").get_json()["items"] if u["username"] == "oper"][0]["id"]
    assert admin.delete(f"/api/users/{oper_id}").status_code == 200
    assert operator.get("/api/databases").status_code == 401
