"""Business logic for saved database connections."""
import logging

from flask import current_app

from ..adapters import get_adapter
from ..exceptions import ConflictError, NotFoundError, ValidationError
from ..models.database_connection import DatabaseConnection
from ..repositories import database_repository, schedule_repository
from . import encryption_service

log = logging.getLogger("dbsafe")


def get_connection(connection_id):
    connection = database_repository.get(connection_id)
    if connection is None:
        raise NotFoundError("Database connection not found")
    return connection


def adapter_params(connection, database=None):
    password = ""
    if connection.credential_reference:
        password = encryption_service.decrypt_secret(connection.credential_reference)
    return {
        "host": connection.host, "port": connection.port, "username": connection.username,
        "password": password, "database_name": database or connection.database_name,
        "extra": connection.extra_dict(),
    }


def build_adapter(connection, database=None):
    return get_adapter(connection.database_type, adapter_params(connection, database),
                       current_app.config)


def create_connection(data):
    if database_repository.get_by_name(data["name"]):
        raise ConflictError("A connection with this name already exists")
    record = {k: data.get(k) for k in ("name", "database_type", "host", "port", "username",
                                        "database_name", "extra")}
    if data.get("password"):
        record["credential_reference"] = encryption_service.encrypt_secret(data["password"])
    new_id = database_repository.create(record)
    return get_connection(new_id)


def update_connection(connection_id, data):
    existing = get_connection(connection_id)
    clash = database_repository.get_by_name(data["name"])
    if clash and clash.id != existing.id:
        raise ConflictError("A connection with this name already exists")
    fields = {k: data.get(k) for k in ("name", "database_type", "host", "port", "username",
                                        "database_name", "extra")}
    if data.get("password"):  # empty password on edit keeps the stored one
        fields["credential_reference"] = encryption_service.encrypt_secret(data["password"])
    elif data["database_type"] == "sqlite":
        fields["credential_reference"] = None
    database_repository.update(connection_id, fields)
    return get_connection(connection_id)


def delete_connection(connection_id):
    from . import scheduler_service
    connection = get_connection(connection_id)
    for schedule in schedule_repository.list_for_connection(connection_id):
        scheduler_service.unregister_schedule(schedule.id)
    database_repository.delete(connection_id)  # schedules cascade; backups keep their history
    return connection


def test_connection(connection):
    adapter = build_adapter(connection)
    return adapter.test_connection()


def test_payload(data, existing_id=None):
    """Test unsaved connection details. An empty password reuses the stored one."""
    params = {k: data.get(k) for k in ("host", "port", "username", "database_name", "extra")}
    params["password"] = data.get("password") or ""
    if not params["password"] and existing_id:
        existing = get_connection(existing_id)
        if existing.credential_reference:
            params["password"] = encryption_service.decrypt_secret(existing.credential_reference)
    adapter = get_adapter(data["database_type"], params, current_app.config)
    return adapter.test_connection()


def list_tables(connection):
    adapter = build_adapter(connection)
    try:
        return adapter.get_tables()
    finally:
        adapter.disconnect()


def database_information(connection):
    adapter = build_adapter(connection)
    try:
        return adapter.get_database_information()
    finally:
        adapter.disconnect()


def validate_target_database(connection, target):
    """Validate a restore target name for *connection* and return the effective name."""
    from pathlib import Path
    from ..utils.validation import validate_identifier

    if not target:
        return connection.database_name
    if connection.database_type == "sqlite":
        own = Path(connection.database_name).resolve()
        candidate = Path(target).expanduser().resolve()
        allowed_suffix = candidate.suffix.lower() in (".db", ".sqlite", ".sqlite3")
        if candidate != own and not (candidate.parent == own.parent and allowed_suffix):
            raise ValidationError(
                "For SQLite the restore target must be the connection's own file or a "
                ".db/.sqlite/.sqlite3 file in the same folder.")
        return str(candidate)
    return validate_identifier(target, "target database")
