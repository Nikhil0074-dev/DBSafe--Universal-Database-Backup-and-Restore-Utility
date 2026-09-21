import json

from ..models.restore import Restore
from . import base

_COLUMNS = {"backup_id", "backup_code", "connection_id", "connection_name", "target_database",
            "status", "safety_backup_code", "verification_result", "started_at", "completed_at",
            "duration_seconds", "error_message", "initiated_by"}


def create(data):
    columns = [key for key in data if key in _COLUMNS]
    placeholders = ", ".join("?" for _ in columns)
    return base.execute(
        f"INSERT INTO restore_logs ({', '.join(columns)}) VALUES ({placeholders})",
        [data[key] for key in columns])


def update(restore_pk, **fields):
    if "verification_result" in fields and not isinstance(fields["verification_result"], (str, type(None))):
        fields["verification_result"] = json.dumps(fields["verification_result"])
    base.update_row("restore_logs", restore_pk, fields, _COLUMNS)


def get(restore_pk):
    return Restore.from_row(base.fetch_one("SELECT * FROM restore_logs WHERE id = ?", (restore_pk,)))


def list_restores(limit=100):
    rows = base.fetch_all("SELECT * FROM restore_logs ORDER BY started_at DESC, id DESC LIMIT ?", (limit,))
    return [Restore.from_row(r) for r in rows]


def mark_running_as_failed():
    return base.execute_count(
        "UPDATE restore_logs SET status = 'failed', error_message = 'Interrupted by application restart' "
        "WHERE status = 'running'")
