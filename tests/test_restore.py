import sqlite3
import time
from pathlib import Path

from tests.conftest import count_rows
from tests.test_backup import make_backup


def restore(client, backup, connection, **kw):
    payload = {"backup_id": backup["id"], "connection_id": connection["id"], "confirm": True, "sync": True}
    payload.update(kw)
    return client.post("/api/restore", payload)


def test_restore_into_new_database(admin, connection, sample_db, tmp_path):
    b = make_backup(admin, connection, encryption=True, compression="gzip")
    target = tmp_path / "shop_restore.db"
    r = restore(admin, b, connection, target_database=str(target))
    body = r.get_json()
    assert r.status_code == 201 and body["status"] == "success", body
    assert count_rows(target, "users") == 50 and count_rows(target, "products") == 200
    steps = [s["step"] for s in body["verification_result"]["steps"]]
    assert "Decrypt backup" in steps and "Decompress backup" in steps
    skipped = [s for s in body["verification_result"]["steps"] if s["status"] == "skipped"]
    assert skipped  # target did not exist, so no safety backup was needed


def test_restore_overwrites_with_safety_backup(admin, connection, sample_db):
    b = make_backup(admin, connection)
    conn = sqlite3.connect(sample_db)
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    assert count_rows(sample_db, "users") == 0
    r = restore(admin, b, connection)
    body = r.get_json()
    assert body["status"] == "success", body
    assert count_rows(sample_db, "users") == 50
    assert body["safety_backup_code"]
    safety = admin.get(f"/api/backups/{body['safety_backup_code']}").get_json()
    assert safety["kind"] == "safety" and safety["status"] == "success"


def test_restore_requires_confirmation_and_valid_backup(admin, connection):
    b = make_backup(admin, connection)
    r = admin.post("/api/restore", {"backup_id": b["id"], "connection_id": connection["id"]})
    assert r.status_code == 400
    assert restore(admin, {"id": 9999}, connection).status_code == 404


def test_restore_refuses_tampered_backup(admin, connection, app, sample_db):
    b = make_backup(admin, connection)
    path = Path(app.config["BACKUP_DIR"]) / "sqlite" / b["file_name"]
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    conn = sqlite3.connect(sample_db)
    conn.execute("DELETE FROM orders")
    conn.commit()
    conn.close()
    body = restore(admin, b, connection).get_json()
    assert body["status"] == "failed" and "integrity" in body["error_message"].lower()
    assert count_rows(sample_db, "orders") == 0  # untouched


def test_restore_type_mismatch(admin, connection):
    b = make_backup(admin, connection)
    other = admin.post("/api/databases", {"name": "pg", "database_type": "postgresql", "username": "u",
                                          "database_name": "x"}).get_json()
    r = restore(admin, b, other)
    assert r.status_code == 400 and "cannot be restored" in r.get_json()["error"]


def test_sqlite_target_restriction(admin, connection, tmp_path):
    b = make_backup(admin, connection)
    r = restore(admin, b, connection, target_database="/etc/passwd")
    assert r.status_code == 400
    elsewhere = tmp_path.parent / "other_dir" / "x.db"
    assert restore(admin, b, connection, target_database=str(elsewhere)).status_code == 400
    assert restore(admin, b, connection, target_database=str(tmp_path / "ok.sqlite")).status_code == 201


def test_wrong_encryption_key_fails_cleanly(admin, connection, app, tmp_path):
    b = make_backup(admin, connection, encryption=True)
    app.config["ENCRYPTION_KEY"] = "a-completely-different-key"
    body = restore(admin, b, connection, target_database=str(tmp_path / "r.db")).get_json()
    assert body["status"] == "failed"
    assert "wrong encryption key" in body["error_message"]


def test_restore_history_and_operator_access(admin, operator, connection, tmp_path):
    b = make_backup(operator, connection)
    r = restore(operator, b, connection, target_database=str(tmp_path / "op.db"))
    assert r.get_json()["status"] == "success"
    items = admin.get("/api/restores").get_json()["items"]
    assert items and items[0]["backup_code"] == b["backup_id"] and items[0]["initiated_by"] == "oper"
    assert admin.get(f"/api/restores/{items[0]['id']}").status_code == 200
    assert admin.get("/api/restores/9999").status_code == 404


def test_async_restore(admin, connection, tmp_path):
    b = make_backup(admin, connection)
    r = admin.post("/api/restore", {"backup_id": b["id"], "connection_id": connection["id"],
                                    "confirm": True, "target_database": str(tmp_path / "a.db")})
    assert r.status_code == 202
    rid = r.get_json()["id"]
    for _ in range(100):
        row = admin.get(f"/api/restores/{rid}").get_json()
        if row["status"] != "running":
            break
        time.sleep(0.1)
    assert row["status"] == "success"
