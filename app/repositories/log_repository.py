import logging

from ..models.operation_log import OperationLog
from ..utils.datetime_utils import now_str
from . import base

log = logging.getLogger("dbsafe")


def add(operation, status, message="", database_name=None, user=None):
    """Write an audit-log entry. Never raises: logging must not break operations."""
    user = user or {}
    try:
        base.execute(
            """INSERT INTO operation_logs (user_id, username, operation, database_name, status, message, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user.get("id"), user.get("username") or "system", operation, database_name,
             status, (message or "")[:2000], now_str()))
    except Exception:  # pragma: no cover - defensive
        log.exception("Could not write operation log entry")


def search(*, q=None, status=None, operation=None, page=1, per_page=50):
    where, params = [], []
    if q:
        like = f"%{q}%"
        where.append("(message LIKE ? OR database_name LIKE ? OR username LIKE ?)")
        params += [like, like, like]
    if status:
        where.append("status = ?")
        params.append(status)
    if operation:
        where.append("operation = ?")
        params.append(operation)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    per_page = max(1, min(int(per_page), 200))
    page = max(1, int(page))
    total = base.fetch_one(f"SELECT COUNT(*) AS n FROM operation_logs {clause}", params)["n"]
    rows = base.fetch_all(
        f"SELECT * FROM operation_logs {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page])
    return [OperationLog.from_row(r) for r in rows], total
