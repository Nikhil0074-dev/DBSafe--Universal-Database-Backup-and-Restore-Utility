from flask import Blueprint, current_app, jsonify

from ..exceptions import NotFoundError
from ..extensions import run_in_background
from ..repositories import restore_repository
from ..services import restore_service
from ..utils.validation import validate_restore_payload
from .security import current_user, json_body, login_required

bp = Blueprint("restores", __name__, url_prefix="/api")


@bp.post("/restore")
@login_required
def restore():
    user = current_user()
    data = validate_restore_payload(json_body())
    row, options = restore_service.prepare_restore(
        data["backup_id"], data["connection_id"], data["target_database"],
        data["safety_backup"], user)
    if data["sync"]:
        row = restore_service.execute_restore(row.id, options)
        return jsonify(row.to_dict()), 201
    run_in_background(current_app._get_current_object(), restore_service.execute_restore,
                      row.id, options)
    return jsonify(row.to_dict()), 202


@bp.get("/restores")
@login_required
def list_restores():
    return jsonify(items=[r.to_dict() for r in restore_repository.list_restores()])


@bp.get("/restores/<int:restore_id>")
@login_required
def get_restore(restore_id):
    row = restore_repository.get(restore_id)
    if row is None:
        raise NotFoundError("Restore not found")
    return jsonify(row.to_dict())
