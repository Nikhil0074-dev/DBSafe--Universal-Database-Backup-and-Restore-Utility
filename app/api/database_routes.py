from flask import Blueprint, jsonify

from ..repositories import database_repository, log_repository
from ..services import connection_service
from ..utils.validation import clean_int, validate_connection_payload
from .security import admin_required, current_user, json_body, login_required

bp = Blueprint("databases", __name__, url_prefix="/api")


@bp.get("/databases")
@login_required
def list_databases():
    return jsonify(items=[c.to_dict() for c in database_repository.list_connections()])


@bp.post("/databases")
@admin_required
def create_database():
    data = validate_connection_payload(json_body())
    connection = connection_service.create_connection(data)
    log_repository.add("add_database", "success", f"Added connection '{connection.name}'",
                       connection.database_name, current_user())
    return jsonify(connection.to_dict()), 201


@bp.post("/databases/test")
@admin_required
def test_unsaved():
    body = json_body()
    data = validate_connection_payload(body)
    existing_id = clean_int(body, "connection_id", minimum=1)
    return jsonify(connection_service.test_payload(data, existing_id))


@bp.get("/databases/<int:connection_id>")
@login_required
def get_database(connection_id):
    return jsonify(connection_service.get_connection(connection_id).to_dict())


@bp.put("/databases/<int:connection_id>")
@admin_required
def update_database(connection_id):
    data = validate_connection_payload(json_body())
    connection = connection_service.update_connection(connection_id, data)
    log_repository.add("update_database", "success", f"Updated connection '{connection.name}'",
                       connection.database_name, current_user())
    return jsonify(connection.to_dict())


@bp.delete("/databases/<int:connection_id>")
@admin_required
def delete_database(connection_id):
    connection = connection_service.delete_connection(connection_id)
    log_repository.add("delete_database", "success", f"Deleted connection '{connection.name}'",
                       connection.database_name, current_user())
    return jsonify(ok=True)


@bp.post("/databases/<int:connection_id>/test")
@login_required
def test_saved(connection_id):
    connection = connection_service.get_connection(connection_id)
    result = connection_service.test_connection(connection)
    log_repository.add("test_connection", "success" if result["ok"] else "failed",
                       result["message"], connection.database_name, current_user())
    return jsonify(result)


@bp.get("/databases/<int:connection_id>/tables")
@login_required
def tables(connection_id):
    connection = connection_service.get_connection(connection_id)
    return jsonify(items=connection_service.list_tables(connection))


@bp.get("/databases/<int:connection_id>/info")
@login_required
def info(connection_id):
    connection = connection_service.get_connection(connection_id)
    return jsonify(connection_service.database_information(connection))
