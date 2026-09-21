import json

from ..models.database_connection import DatabaseConnection
from . import base

_COLUMNS = {"name", "database_type", "host", "port", "username", "database_name",
            "credential_reference", "extra"}


def count():
    return base.fetch_one("SELECT COUNT(*) AS n FROM database_connections")["n"]


def list_connections():
    rows = base.fetch_all("SELECT * FROM database_connections ORDER BY name")
    return [DatabaseConnection.from_row(r) for r in rows]


def get(connection_id):
    return DatabaseConnection.from_row(
        base.fetch_one("SELECT * FROM database_connections WHERE id = ?", (connection_id,)))


def get_by_name(name):
    return DatabaseConnection.from_row(
        base.fetch_one("SELECT * FROM database_connections WHERE name = ?", (name,)))


def create(data):
    return base.execute(
        """INSERT INTO database_connections
           (name, database_type, host, port, username, database_name, credential_reference, extra)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (data["name"], data["database_type"], data.get("host"), data.get("port"),
         data.get("username"), data["database_name"], data.get("credential_reference"),
         json.dumps(data.get("extra") or {})))


def update(connection_id, fields):
    fields = dict(fields)
    if "extra" in fields and not isinstance(fields["extra"], str):
        fields["extra"] = json.dumps(fields["extra"] or {})
    base.update_row("database_connections", connection_id, fields, _COLUMNS)


def delete(connection_id):
    return base.execute_count("DELETE FROM database_connections WHERE id = ?", (connection_id,))
