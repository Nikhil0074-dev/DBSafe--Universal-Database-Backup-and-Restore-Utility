import sqlite3

from app.repositories import base


def test_create_test_and_list_sqlite(admin, connection):
    assert connection["database_type"] == "sqlite"
    r = admin.post(f"/api/databases/{connection['id']}/test")
    body = r.get_json()
    assert r.status_code == 200 and body["ok"] is True
    assert body["tables"] == 3
    tables = admin.get(f"/api/databases/{connection['id']}/tables").get_json()["items"]
    assert tables == ["orders", "products", "users"]
    info = admin.get(f"/api/databases/{connection['id']}/info").get_json()
    assert info["tables"] == 3 and info["size_bytes"] > 0


def test_connection_failure_reports_reason(admin, tmp_path):
    r = admin.post("/api/databases", {"name": "Missing", "database_type": "sqlite",
                                      "database_name": str(tmp_path / "nope.db")})
    cid = r.get_json()["id"]
    result = admin.post(f"/api/databases/{cid}/test").get_json()
    assert result["ok"] is False and "not found" in result["message"]


def test_not_a_sqlite_file(admin, tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_text("this is not a database" * 50)
    cid = admin.post("/api/databases", {"name": "Bad", "database_type": "sqlite",
                                        "database_name": str(bad)}).get_json()["id"]
    assert admin.post(f"/api/databases/{cid}/test").get_json()["ok"] is False


def test_password_is_encrypted_and_never_returned(app, admin):
    r = admin.post("/api/databases", {"name": "My", "database_type": "mysql", "host": "localhost",
                                      "username": "root", "password": "SuperSecret!", "database_name": "shop"})
    assert r.status_code == 201
    data = r.get_json()
    assert data["has_password"] is True and "SuperSecret" not in str(data)
    assert data["port"] == 3306
    with app.app_context():
        row = base.fetch_one("SELECT credential_reference FROM database_connections WHERE id = ?", (data["id"],))
    assert row["credential_reference"] and "SuperSecret" not in row["credential_reference"]
    assert "SuperSecret" not in str(admin.get("/api/databases").get_json())
    # editing with an empty password keeps the stored secret
    r = admin.put(f"/api/databases/{data['id']}", {"name": "My2", "database_type": "mysql", "host": "db",
                                                    "username": "root", "database_name": "shop"})
    assert r.status_code == 200 and r.get_json()["has_password"] is True


def test_validation_and_conflicts(admin):
    assert admin.post("/api/databases", {"name": "x", "database_type": "oracle", "database_name": "a"}).status_code == 400
    assert admin.post("/api/databases", {"name": "x", "database_type": "mysql", "username": "u",
                                         "database_name": "a; DROP TABLE x"}).status_code == 400
    assert admin.post("/api/databases", {"name": "x", "database_type": "mysql", "username": "u",
                                         "port": 99999, "database_name": "a"}).status_code == 400
    assert admin.post("/api/databases", {"name": "x", "database_type": "mysql",
                                         "database_name": "a"}).status_code == 400  # username required
    ok = {"name": "dup", "database_type": "postgresql", "username": "u", "database_name": "a"}
    assert admin.post("/api/databases", ok).status_code == 201
    assert admin.post("/api/databases", ok).status_code == 409


def test_missing_driver_or_server_is_reported_not_raised(admin):
    cid = admin.post("/api/databases", {"name": "pg", "database_type": "postgresql", "host": "127.0.0.1",
                                        "port": 1, "username": "u", "password": "p",
                                        "database_name": "a"}).get_json()["id"]
    result = admin.post(f"/api/databases/{cid}/test").get_json()
    assert result["ok"] is False and result["message"]


def test_unsaved_test_and_delete(admin, sample_db):
    r = admin.post("/api/databases/test", {"name": "t", "database_type": "sqlite",
                                           "database_name": str(sample_db)})
    assert r.get_json()["ok"] is True
    cid = admin.post("/api/databases", {"name": "t", "database_type": "sqlite",
                                        "database_name": str(sample_db)}).get_json()["id"]
    assert admin.delete(f"/api/databases/{cid}").status_code == 200
    assert admin.get(f"/api/databases/{cid}").status_code == 404
