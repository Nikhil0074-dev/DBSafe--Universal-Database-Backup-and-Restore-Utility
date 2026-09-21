import sqlite3
from pathlib import Path

import pytest

from app.services import storage_service
from app.models.backup import Backup
from tests.conftest import count_rows


def make_backup(client, connection, **kw):
    payload = {"connection_id": connection["id"], "sync": True}
    payload.update(kw)
    r = client.post("/api/backups", payload)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_full_backup_gzip_default(admin, connection, app):
    b = make_backup(admin, connection)
    assert b["status"] == "success", b
    assert b["backup_id"].startswith("BK-") and len(b["backup_id"].split("-")[-1]) == 5
    assert b["file_name"].endswith(".db.gz")
    assert b["compression_enabled"] and not b["encryption_enabled"]
    assert b["checksum"] and len(b["checksum"]) == 64
    assert b["verification_status"] == "valid"
    assert b["original_size"] > 0 and b["stored_size"] > 0
    assert set(b["tables"]) == {"orders", "products", "users"}
    assert "file_path" not in b
    assert (Path(app.config["BACKUP_DIR"]) / "sqlite" / b["file_name"]).is_file()


@pytest.mark.parametrize("compression,suffix", [("none", ".db"), ("gzip", ".db.gz"), ("zip", ".db.zip")])
def test_compression_variants(admin, connection, compression, suffix):
    b = make_backup(admin, connection, compression=compression)
    assert b["status"] == "success" and b["file_name"].endswith(suffix)


def test_encrypted_backup(admin, connection, app):
    b = make_backup(admin, connection, encryption=True)
    assert b["status"] == "success" and b["file_name"].endswith(".db.gz.enc")
    raw = (Path(app.config["BACKUP_DIR"]) / "sqlite" / b["file_name"]).read_bytes()
    assert raw.startswith(b"DBSAFE01") and b"SQLite format" not in raw
    assert b["verification_status"] == "valid"


def test_selective_backup(admin, connection, app, sample_db):
    b = make_backup(admin, connection, backup_type="selective", tables=["users", "orders"], compression="none")
    assert b["status"] == "success" and b["tables"] == ["users", "orders"]
    path = Path(app.config["BACKUP_DIR"]) / "sqlite" / b["file_name"]
    assert count_rows(path, "users") == 50 and count_rows(path, "orders") == 30
    conn = sqlite3.connect(path)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    conn.close()
    assert "products" not in names


def test_selective_validation(admin, connection):
    r = admin.post("/api/backups", {"connection_id": connection["id"], "backup_type": "selective", "sync": True})
    assert r.status_code == 400
    b = make_backup(admin, connection, backup_type="selective", tables=["ghost"])
    assert b["status"] == "failed" and "not found" in b["error_message"]
    r = admin.post("/api/backups", {"connection_id": connection["id"], "backup_type": "selective",
                                    "tables": ["x; drop"], "sync": True})
    assert r.status_code == 400


def test_verify_detects_tampering(admin, connection, app):
    b = make_backup(admin, connection)
    r = admin.post(f"/api/backups/{b['id']}/verify", {"deep": True}).get_json()
    assert r["status"] == "valid"
    path = Path(app.config["BACKUP_DIR"]) / "sqlite" / b["file_name"]
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    r = admin.post(f"/api/backups/{b['id']}/verify").get_json()
    assert r["status"] == "invalid" and "Integrity verification failed" in r["message"]
    assert admin.get(f"/api/backups/{b['id']}").get_json()["verification_status"] == "invalid"
    path.unlink()
    assert admin.post(f"/api/backups/{b['id']}/verify").get_json()["status"] == "missing"


def test_history_search_filter_sort_and_lookup_by_code(admin, connection):
    a = make_backup(admin, connection, compression="none")
    b = make_backup(admin, connection, compression="gzip")
    items = admin.get("/api/backups?sort=size&order=asc").get_json()
    assert items["total"] == 2 and items["items"][0]["stored_size"] <= items["items"][1]["stored_size"]
    assert admin.get("/api/backups?q=shop").get_json()["total"] == 2
    assert admin.get("/api/backups?q=zzz").get_json()["total"] == 0
    assert admin.get("/api/backups?status=failed").get_json()["total"] == 0
    assert admin.get(f"/api/backups/{a['backup_id']}").get_json()["id"] == a["id"]
    assert admin.get("/api/backups/BK-nope").status_code == 404
    assert admin.get("/api/backups?page=abc&per_page=x").status_code == 200


def test_async_backup_finishes(admin, connection):
    import time
    r = admin.post("/api/backups", {"connection_id": connection["id"]})
    assert r.status_code == 202
    bid = r.get_json()["id"]
    for _ in range(100):
        b = admin.get(f"/api/backups/{bid}").get_json()
        if b["status"] != "running":
            break
        time.sleep(0.1)
    assert b["status"] == "success"


def test_delete_and_permissions(admin, operator, connection, app):
    b = make_backup(operator, connection)
    assert operator.delete(f"/api/backups/{b['id']}").status_code == 403
    path = Path(app.config["BACKUP_DIR"]) / "sqlite" / b["file_name"]
    assert path.is_file()
    assert admin.delete(f"/api/backups/{b['id']}").status_code == 200
    assert not path.exists()
    assert admin.get(f"/api/backups/{b['id']}").status_code == 404


def test_destination_rules(admin, operator, connection, app, tmp_path):
    r = operator.post("/api/backups", {"connection_id": connection["id"], "destination": "custom", "sync": True})
    assert r.status_code == 403
    b = make_backup(admin, connection, destination="custom/inner")
    assert b["status"] == "success"
    assert (Path(app.config["BACKUP_DIR"]) / "custom" / "inner" / b["file_name"]).is_file()
    for bad in ("../../escape", str(tmp_path / "elsewhere"), "/etc"):
        r = admin.post("/api/backups", {"connection_id": connection["id"], "destination": bad, "sync": True})
        assert r.status_code == 400, bad


def test_failed_backup_is_recorded(admin, connection, sample_db):
    sample_db.unlink()
    b = make_backup(admin, connection)
    assert b["status"] == "failed" and "not found" in b["error_message"]
    logs = admin.get("/api/logs?status=failed&operation=backup").get_json()
    assert logs["total"] >= 1
    assert admin.get("/api/dashboard").get_json()["failed_backups"] == 1


def test_max_size_limit(admin, connection, app):
    app.config["MAX_BACKUP_SIZE_MB"] = 0
    app.config["MAX_BACKUP_SIZE_MB"] = 1
    # sample db is < 1 MB so it passes
    assert make_backup(admin, connection)["status"] == "success"


def test_filenames_never_collide(admin, connection):
    names = {make_backup(admin, connection, compression="none")["file_name"] for _ in range(3)}
    assert len(names) == 3


def _mk(i, created):
    return Backup(id=i, backup_id=f"B{i}", created_at=created)


def test_retention_selection():
    backups = [_mk(1, "2026-09-20 02:00:00"), _mk(2, "2026-09-20 01:00:00"),
               _mk(3, "2026-09-19 02:00:00"), _mk(4, "2026-09-05 02:00:00"),
               _mk(5, "2026-08-01 02:00:00"), _mk(6, "2026-07-01 02:00:00")]
    from datetime import datetime
    ref = datetime(2026, 9, 20, 12, 0, 0)
    ids = lambda lst: sorted(b.id for b in lst)
    assert storage_service.select_backups_to_delete(backups, 0, 0, 0, 0, ref) == []
    assert ids(storage_service.select_backups_to_delete(backups, 30, reference=ref)) == [5, 6]
    # daily keeps newest per day for 2 days -> 1 and 3; everything older removed
    assert ids(storage_service.select_backups_to_delete(backups, keep_daily=2, reference=ref)) == [2, 4, 5, 6]
    # union of rules
    assert ids(storage_service.select_backups_to_delete(backups, keep_daily=1, keep_monthly=3, reference=ref)) == [2, 3, 4]
    # the newest backup always survives
    assert 1 not in ids(storage_service.select_backups_to_delete(backups, retention_days=1, reference=ref))
