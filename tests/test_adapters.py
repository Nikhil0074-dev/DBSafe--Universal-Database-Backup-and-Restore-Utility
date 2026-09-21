"""External-tool adapters are tested with a fake command runner (no servers required)."""
import os
from pathlib import Path

import pytest

from app.adapters import get_adapter
from app.adapters import mongodb_adapter, mysql_adapter, postgres_adapter
from app.exceptions import ValidationError

PARAMS = {"host": "db.local", "port": 3306, "username": "root", "password": 'p"a\\ss',
          "database_name": "shop", "extra": {}}


@pytest.fixture()
def calls(monkeypatch, tmp_path):
    captured = []

    def fake_run(args, env=None, stdin_path=None, timeout=None, secrets=()):
        record = {"args": list(args), "env": env, "stdin": stdin_path}
        for a in args:
            if str(a).startswith(("--defaults-extra-file=", "--config=")):
                record["config_text"] = Path(str(a).split("=", 1)[1]).read_text()
        captured.append(record)
        for a in args:
            if str(a).startswith("--result-file="):
                Path(str(a).split("=", 1)[1]).write_text("-- dump")
        return ""

    for module in (mysql_adapter, postgres_adapter, mongodb_adapter):
        monkeypatch.setattr(module, "run_command", fake_run)
    monkeypatch.setattr("app.adapters.base_adapter.find_executable", lambda name, configured=None: f"/usr/bin/{name}")
    return captured


def cfg(tmp_path):
    return {"TEMP_DIR": str(tmp_path)}


def test_mysql_backup_never_puts_password_on_command_line(calls, tmp_path):
    adapter = get_adapter("mysql", PARAMS, cfg(tmp_path))
    dest = tmp_path / "out.sql"
    adapter.create_backup(dest, tables=["users", "orders"])
    call = calls[0]
    assert "p\"a" not in " ".join(call["args"])
    assert call["args"][1].startswith("--defaults-extra-file=")
    assert 'password="p\\"a\\\\ss"' in call["config_text"]
    assert call["args"][-3:] == ["shop", "users", "orders"]
    assert "--single-transaction" in call["args"]
    assert not list(tmp_path.glob("dbsafe_*.cnf"))  # temp option file cleaned up


def test_mysql_rejects_unsafe_names(calls, tmp_path):
    with pytest.raises(ValidationError):
        get_adapter("mysql", {**PARAMS, "database_name": "x; drop"}, cfg(tmp_path)).create_backup(tmp_path / "o")
    with pytest.raises(ValidationError):
        get_adapter("mysql", PARAMS, cfg(tmp_path)).create_backup(tmp_path / "o", tables=["a b"])


def test_postgres_backup_uses_env_password(calls, tmp_path):
    adapter = get_adapter("postgresql", {**PARAMS, "port": 5432, "password": "s3cret"}, cfg(tmp_path))
    adapter.create_backup(tmp_path / "o.sql", tables=["public.users"])
    call = calls[0]
    assert "s3cret" not in " ".join(call["args"])
    assert call["env"]["PGPASSWORD"] == "s3cret"
    assert "--table" in call["args"] and "public.users" in call["args"]
    assert call["args"][-1] == "shop"
    with pytest.raises(ValidationError):
        adapter.create_backup(tmp_path / "o.sql", tables=["x;y"])


def test_mongodb_backup_uses_config_file(calls, tmp_path):
    adapter = get_adapter("mongodb", {**PARAMS, "port": 27017, "password": "p@ss/word"}, cfg(tmp_path))
    adapter.create_backup(tmp_path / "o.archive")
    call = calls[0]
    assert "p%40ss%2Fword" in call["config_text"]
    assert not any("p@ss" in a for a in call["args"])
    assert "--nsInclude=shop.*" in call["args"]


def test_mongodb_restore_maps_namespace(calls, tmp_path):
    adapter = get_adapter("mongodb", {**PARAMS, "database_name": "copy"}, cfg(tmp_path))
    adapter.restore_backup(tmp_path / "a.archive", source_database="shop")
    args = calls[0]["args"]
    assert "--nsFrom=shop.*" in args and "--nsTo=copy.*" in args


def test_unknown_type():
    with pytest.raises(ValidationError):
        get_adapter("oracle", PARAMS, {})


def test_unreachable_servers_report_errors_not_exceptions(tmp_path):
    for db_type, port in (("mysql", 1), ("postgresql", 1), ("mongodb", 1)):
        adapter = get_adapter(db_type, {**PARAMS, "host": "127.0.0.1", "port": port, "password": "pw"},
                              cfg(tmp_path))
        result = adapter.test_connection()
        assert result["ok"] is False and result["message"] and "pw" != result["message"]
