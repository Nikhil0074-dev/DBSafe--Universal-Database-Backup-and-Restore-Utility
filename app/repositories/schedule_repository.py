import json

from ..models.schedule import Schedule
from . import base

_COLUMNS = {"connection_id", "name", "frequency", "schedule_time", "day_of_week", "day_of_month",
            "cron_expression", "backup_type", "tables", "compression", "encryption", "verify",
            "destination", "retention_days", "keep_daily", "keep_weekly", "keep_monthly",
            "enabled", "last_run_at", "last_status"}


def _prepare(data):
    data = dict(data)
    if isinstance(data.get("tables"), (list, tuple)):
        data["tables"] = json.dumps(list(data["tables"]))
    for key in ("encryption", "verify", "enabled"):
        if key in data:
            data[key] = 1 if data[key] else 0
    return data


def list_schedules():
    return [Schedule.from_row(r) for r in base.fetch_all("SELECT * FROM schedules ORDER BY id")]


def list_enabled():
    return [Schedule.from_row(r) for r in base.fetch_all("SELECT * FROM schedules WHERE enabled = 1")]


def list_for_connection(connection_id):
    return [Schedule.from_row(r) for r in
            base.fetch_all("SELECT * FROM schedules WHERE connection_id = ?", (connection_id,))]


def count_enabled():
    return base.fetch_one("SELECT COUNT(*) AS n FROM schedules WHERE enabled = 1")["n"]


def get(schedule_id):
    return Schedule.from_row(base.fetch_one("SELECT * FROM schedules WHERE id = ?", (schedule_id,)))


def create(data):
    data = _prepare(data)
    columns = [key for key in data if key in _COLUMNS]
    placeholders = ", ".join("?" for _ in columns)
    return base.execute(
        f"INSERT INTO schedules ({', '.join(columns)}) VALUES ({placeholders})",
        [data[key] for key in columns])


def update(schedule_id, **fields):
    base.update_row("schedules", schedule_id, _prepare(fields), _COLUMNS)


def delete(schedule_id):
    return base.execute_count("DELETE FROM schedules WHERE id = ?", (schedule_id,))
