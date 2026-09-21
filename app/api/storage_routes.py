from flask import Blueprint, jsonify

from ..repositories import backup_repository, database_repository, log_repository, schedule_repository
from ..services import storage_service
from .security import admin_required, current_user, login_required

bp = Blueprint("storage", __name__, url_prefix="/api")


@bp.get("/storage")
@login_required
def storage():
    return jsonify(storage_service.overview())


@bp.post("/storage/cleanup")
@admin_required
def cleanup():
    removed = storage_service.apply_retention_all(current_user())
    log_repository.add("retention_cleanup", "success", f"Removed {removed} expired backup(s)",
                       None, current_user())
    return jsonify(ok=True, removed=removed)


@bp.get("/dashboard")
@login_required
def dashboard():
    stats = backup_repository.stats()
    return jsonify(
        databases=database_repository.count(),
        successful_backups=stats["successful"],
        failed_backups=stats["failed"],
        running_backups=stats["running"],
        total_storage=stats["total_size"],
        scheduled_backups=schedule_repository.count_enabled(),
        recent=[b.to_dict() for b in backup_repository.recent(5)],
    )
