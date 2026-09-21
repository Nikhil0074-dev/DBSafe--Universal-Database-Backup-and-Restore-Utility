from flask import Blueprint, current_app, jsonify, request

from ..exceptions import PermissionDenied
from ..repositories import backup_repository
from ..services import backup_service, storage_service, verification_service
from ..extensions import run_in_background
from ..utils.validation import clean_bool, clean_int, validate_backup_payload
from .security import admin_required, current_user, json_body, login_required

bp = Blueprint("backups", __name__, url_prefix="/api")


@bp.get("/backups")
@login_required
def list_backups():
    args = request.args
    try:
        page = int(args.get("page", 1))
        per_page = int(args.get("per_page", 20))
        connection_id = int(args["connection_id"]) if args.get("connection_id") else None
    except ValueError:
        page, per_page, connection_id = 1, 20, None
    items, total = backup_repository.search(
        q=(args.get("q") or "").strip() or None,
        status=args.get("status") or None,
        connection_id=connection_id,
        kind=args.get("kind") or None,
        sort=args.get("sort", "created_at"),
        order=args.get("order", "desc"),
        page=page, per_page=per_page)
    return jsonify(items=[b.to_dict() for b in items], total=total, page=page,
                   per_page=max(1, min(per_page, 200)))


@bp.post("/backups")
@login_required
def create_backup():
    user = current_user()
    data = validate_backup_payload(json_body())
    if data["destination"] and user["role"] != "admin":
        raise PermissionDenied("Only administrators can choose a custom destination")
    options = backup_service.BackupOptions(
        backup_type=data["backup_type"], tables=data["tables"], compression=data["compression"],
        encryption=data["encryption"], verify=data["verify"], destination=data["destination"],
        kind="manual", user=user)
    backup = backup_service.prepare_backup(data["connection_id"], options)
    if data["sync"]:
        backup = backup_service.execute_backup(backup.id, options)
        return jsonify(backup.to_dict()), 201
    run_in_background(current_app._get_current_object(), backup_service.execute_backup,
                      backup.id, options)
    return jsonify(backup.to_dict()), 202


@bp.get("/backups/<identifier>")
@login_required
def get_backup(identifier):
    return jsonify(backup_service.get_backup(identifier).to_dict())


@bp.delete("/backups/<identifier>")
@admin_required
def delete_backup(identifier):
    backup = backup_service.get_backup(identifier)
    storage_service.delete_backup(backup, current_user())
    return jsonify(ok=True)


@bp.post("/backups/<identifier>/verify")
@login_required
def verify_backup(identifier):
    backup = backup_service.get_backup(identifier)
    deep = clean_bool(json_body(), "deep", False)
    result = verification_service.verify_backup(backup, deep=deep, user=current_user())
    return jsonify(result)
