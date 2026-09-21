from flask import Blueprint, current_app, jsonify

from ..exceptions import NotFoundError
from ..extensions import run_in_background
from ..repositories import log_repository, schedule_repository
from ..services import connection_service, scheduler_service
from ..utils.validation import validate_schedule_payload
from .security import admin_required, current_user, json_body, login_required

bp = Blueprint("schedules", __name__, url_prefix="/api")


def _get(schedule_id):
    schedule = schedule_repository.get(schedule_id)
    if schedule is None:
        raise NotFoundError("Schedule not found")
    return schedule


def _serialize(schedule):
    data = schedule.to_dict()
    try:
        data["connection_name"] = connection_service.get_connection(schedule.connection_id).name
    except NotFoundError:
        data["connection_name"] = None
    data["next_run"] = scheduler_service.next_run_time(schedule.id)
    return data


@bp.get("/schedules")
@login_required
def list_schedules():
    return jsonify(items=[_serialize(s) for s in schedule_repository.list_schedules()])


@bp.post("/schedules")
@admin_required
def create_schedule():
    data = validate_schedule_payload(json_body())
    connection_service.get_connection(data["connection_id"])
    new_id = schedule_repository.create(data)
    schedule = _get(new_id)
    scheduler_service.register_schedule(schedule)
    log_repository.add("create_schedule", "success", f"Schedule {new_id} ({schedule.frequency})",
                       None, current_user())
    return jsonify(_serialize(schedule)), 201


@bp.put("/schedules/<int:schedule_id>")
@admin_required
def update_schedule(schedule_id):
    existing = _get(schedule_id).to_dict()
    merged = {k: v for k, v in existing.items()
              if k not in ("id", "last_run_at", "last_status", "created_at")}
    merged.update(json_body())
    data = validate_schedule_payload(merged)
    connection_service.get_connection(data["connection_id"])
    schedule_repository.update(schedule_id, **data)
    schedule = _get(schedule_id)
    scheduler_service.register_schedule(schedule)
    log_repository.add("update_schedule", "success", f"Schedule {schedule_id} updated", None,
                       current_user())
    return jsonify(_serialize(schedule))


@bp.delete("/schedules/<int:schedule_id>")
@admin_required
def delete_schedule(schedule_id):
    _get(schedule_id)
    scheduler_service.unregister_schedule(schedule_id)
    schedule_repository.delete(schedule_id)
    log_repository.add("delete_schedule", "success", f"Schedule {schedule_id} deleted", None,
                       current_user())
    return jsonify(ok=True)


@bp.post("/schedules/<int:schedule_id>/run")
@admin_required
def run_now(schedule_id):
    _get(schedule_id)
    run_in_background(current_app._get_current_object(), scheduler_service.execute_schedule,
                      schedule_id)
    return jsonify(ok=True, message="Scheduled backup started"), 202
