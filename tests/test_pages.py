import pytest

PAGES = ["/", "/databases", "/databases/add", "/backups", "/restore", "/schedules", "/storage",
         "/logs", "/users", "/account"]


@pytest.mark.parametrize("url", PAGES)
def test_admin_pages_render(admin, url):
    r = admin.get(url)
    assert r.status_code == 200
    assert b"DBSafe" in r.data and b"Log out" in r.data


def test_detail_and_edit_pages(admin, connection):
    assert admin.get(f"/databases/{connection['id']}/edit").status_code == 200
    assert admin.get("/databases/9999/edit").status_code == 404
    b = admin.post("/api/backups", {"connection_id": connection["id"], "sync": True}).get_json()
    assert admin.get(f"/backups/{b['id']}").status_code == 200


def test_operator_page_access(operator):
    for url in ("/", "/databases", "/backups", "/restore", "/schedules", "/storage", "/account"):
        assert operator.get(url).status_code == 200, url
    for url in ("/logs", "/users", "/databases/add"):
        assert operator.get(url).status_code == 403, url
    assert b"Create schedule" not in operator.get("/schedules").data


def test_static_assets_and_headers(client):
    for path in ("css/style.css", "js/common.js", "js/backup.js", "images/logo.png"):
        assert client.get("/static/" + path).status_code == 200, path
    r = client.get("/login")
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["X-Content-Type-Options"] == "nosniff"
    assert client.get("/api/nothing").get_json()["error"]


def test_html_is_escaped(admin, sample_db):
    r = admin.post("/api/databases", {"name": "<script>x</script>", "database_type": "sqlite",
                                      "database_name": str(sample_db)})
    assert r.status_code == 201  # stored verbatim; JS escapes on render via DBSafe.esc
    assert b"<script>x</script>" not in admin.get("/databases").data


def test_storage_and_dashboard_api(admin, connection):
    admin.post("/api/backups", {"connection_id": connection["id"], "sync": True})
    s = admin.get("/api/storage").get_json()
    assert s["backup_used"] > 0 and s["total"] > 0 and s["by_database"][0]["database"] == "Shop"
    d = admin.get("/api/dashboard").get_json()
    assert d["successful_backups"] == 1 and d["databases"] == 1 and len(d["recent"]) == 1
    assert admin.post("/api/storage/cleanup").get_json()["ok"] is True
