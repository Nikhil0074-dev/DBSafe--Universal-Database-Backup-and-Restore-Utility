import json

from ..models.backup import Backup
from . import base

_COLUMNS = {
    "backup_id", "connection_id", "connection_name", "database_type", "database_name",
    "backup_type", "kind", "tables", "file_path", "file_name", "original_size",
    "compressed_size", "stored_size", "compression_type", "compression_enabled",
    "encryption_enabled", "checksum", "status", "verification_status", "last_verified_at",
    "duration_seconds", "error_message", "created_by", "created_at",
}
_SORTABLE = {"created_at": "created_at", "size": "stored_size", "database": "database_name",
             "status": "status", "backup_id": "backup_id", "id": "id"}


def create(data):
    data = dict(data)
    if isinstance(data.get("tables"), (list, tuple)):
        data["tables"] = json.dumps(list(data["tables"]))
    columns = [key for key in data if key in _COLUMNS]
    placeholders = ", ".join("?" for _ in columns)
    return base.execute(
        f"INSERT INTO backups ({', '.join(columns)}) VALUES ({placeholders})",
        [data[key] for key in columns])


def update(backup_pk, **fields):
    base.update_row("backups", backup_pk, fields, _COLUMNS)


def get(backup_pk):
    return Backup.from_row(base.fetch_one("SELECT * FROM backups WHERE id = ?", (backup_pk,)))


def get_by_code(code):
    return Backup.from_row(base.fetch_one("SELECT * FROM backups WHERE backup_id = ?", (code,)))


def delete(backup_pk):
    return base.execute_count("DELETE FROM backups WHERE id = ?", (backup_pk,))


def search(*, q=None, status=None, connection_id=None, kind=None, sort="created_at",
           order="desc", page=1, per_page=20):
    where, params = [], []
    if q:
        like = f"%{q}%"
        where.append("(backup_id LIKE ? OR connection_name LIKE ? OR database_name LIKE ? OR file_name LIKE ?)")
        params += [like, like, like, like]
    if status:
        where.append("status = ?")
        params.append(status)
    if connection_id:
        where.append("connection_id = ?")
        params.append(connection_id)
    if kind:
        where.append("kind = ?")
        params.append(kind)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    column = _SORTABLE.get(sort, "created_at")
    direction = "ASC" if str(order).lower() == "asc" else "DESC"
    per_page = max(1, min(int(per_page), 200))
    page = max(1, int(page))
    total = base.fetch_one(f"SELECT COUNT(*) AS n FROM backups {clause}", params)["n"]
    rows = base.fetch_all(
        f"SELECT * FROM backups {clause} ORDER BY {column} {direction}, id DESC LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page])
    return [Backup.from_row(r) for r in rows], total


def list_successful_for_connection(connection_id, kind=None):
    sql = "SELECT * FROM backups WHERE connection_id = ? AND status = 'success'"
    params = [connection_id]
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY created_at DESC, id DESC"
    return [Backup.from_row(r) for r in base.fetch_all(sql, params)]


def recent(limit=5):
    rows = base.fetch_all("SELECT * FROM backups ORDER BY created_at DESC, id DESC LIMIT ?", (limit,))
    return [Backup.from_row(r) for r in rows]


def stats():
    row = base.fetch_one(
        """SELECT
             COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0) AS successful,
             COALESCE(SUM(CASE WHEN status = 'failed'  THEN 1 ELSE 0 END), 0) AS failed,
             COALESCE(SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END), 0) AS running,
             COALESCE(SUM(CASE WHEN status = 'success' THEN stored_size ELSE 0 END), 0) AS total_size
           FROM backups""")
    return row


def storage_by_database():
    return base.fetch_all(
        """SELECT COALESCE(connection_name, database_name, 'Unknown') AS database,
                  COUNT(*) AS backups, COALESCE(SUM(stored_size), 0) AS size
           FROM backups WHERE status = 'success'
           GROUP BY COALESCE(connection_name, database_name, 'Unknown')
           ORDER BY size DESC""")


def mark_running_as_failed():
    return base.execute_count(
        "UPDATE backups SET status = 'failed', error_message = 'Interrupted by application restart' "
        "WHERE status = 'running'")
