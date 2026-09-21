"""Backup storage: destinations, disk usage, deletion and retention."""
import logging
from datetime import timedelta
from pathlib import Path

from flask import current_app

from ..exceptions import BackupError, ValidationError
from ..repositories import backup_repository, log_repository, schedule_repository
from ..utils.datetime_utils import now, parse_datetime
from ..utils.file_utils import disk_usage, ensure_dir, is_within, remove_quietly

log = logging.getLogger("dbsafe")

_FOLDERS = {"mysql": "mysql", "postgresql": "postgres", "sqlite": "sqlite", "mongodb": "mongodb"}


def resolve_destination(db_type, destination=None):
    """Return (and create) the folder a backup is written to.

    A custom destination must lie inside one of the configured allowed roots, which
    prevents path-traversal and writing to arbitrary locations.
    """
    cfg = current_app.config
    if destination:
        path = Path(destination).expanduser()
        if not path.is_absolute():
            path = Path(cfg["BACKUP_DIR"]) / path
        if not is_within(path, cfg["ALLOWED_BACKUP_ROOTS"]):
            raise ValidationError(
                "The destination must be inside an allowed backup location "
                "(see DBSAFE_ALLOWED_BACKUP_ROOTS).")
    else:
        path = Path(cfg["BACKUP_DIR"]) / _FOLDERS.get(db_type, "other")
    try:
        return ensure_dir(path)
    except OSError as exc:
        raise BackupError(f"Cannot create the backup folder: {exc}") from exc


def ensure_free_space(path):
    minimum = int(current_app.config.get("MIN_FREE_MB", 0)) * 1024 * 1024
    free = disk_usage(path).free
    if free < minimum:
        raise BackupError("Insufficient disk space for a backup "
                          f"({free // (1024 * 1024)} MB free, {minimum // (1024 * 1024)} MB required)")


def overview():
    cfg = current_app.config
    usage = disk_usage(cfg["BACKUP_DIR"])
    stats = backup_repository.stats()
    backup_used = int(stats["total_size"])
    capacity_gb = int(cfg.get("STORAGE_CAPACITY_GB") or 0)
    if capacity_gb > 0:
        total = capacity_gb * 1024 ** 3
        used = backup_used
        free = max(total - used, 0)
    else:
        total, used, free = usage.total, usage.used, usage.free
    percent = round(used / total * 100, 1) if total else 0.0
    return {
        "total": total, "used": used, "free": free, "percent_used": percent,
        "backup_used": backup_used,
        "disk_free": usage.free,
        "warn_percent": cfg["STORAGE_WARN_PERCENT"],
        "by_database": backup_repository.storage_by_database(),
    }


def check_storage_and_notify():
    from . import notification_service
    info = overview()
    if info["percent_used"] >= info["warn_percent"]:
        notification_service.notify(
            "storage_full", "Backup storage almost full",
            f"Backup storage is {info['percent_used']}% full.")
        return True
    return False


def delete_backup(backup, user=None):
    """Delete a backup's file and metadata. The file is removed only if it lies in an allowed root."""
    if backup.file_path and is_within(backup.file_path, current_app.config["ALLOWED_BACKUP_ROOTS"]):
        remove_quietly(backup.file_path)
    backup_repository.delete(backup.id)
    log_repository.add("delete_backup", "success", f"Deleted backup {backup.backup_id}",
                       backup.database_name, user)
    log.info("Deleted backup %s", backup.backup_id)


def select_backups_to_delete(backups, retention_days=0, keep_daily=0, keep_weekly=0,
                             keep_monthly=0, reference=None):
    """Pure function: decide which backups a retention policy removes.

    *backups* must be newest-first. The newest backup is always kept. When no
    policy value is set nothing is deleted. Policies combine: a backup survives if
    ANY rule keeps it.
    """
    if not backups or not any((retention_days, keep_daily, keep_weekly, keep_monthly)):
        return []
    reference = reference or now()
    keep = {backups[0].id}

    def keep_newest_per_bucket(limit, bucket_of):
        if not limit:
            return
        seen = []
        for backup in backups:
            created = parse_datetime(backup.created_at)
            if created is None:
                keep.add(backup.id)
                continue
            bucket = bucket_of(created)
            if bucket in seen:
                continue
            if len(seen) >= limit:
                break
            seen.append(bucket)
            keep.add(backup.id)

    keep_newest_per_bucket(keep_daily, lambda d: d.date())
    keep_newest_per_bucket(keep_weekly, lambda d: d.isocalendar()[:2])
    keep_newest_per_bucket(keep_monthly, lambda d: (d.year, d.month))
    if retention_days:
        cutoff = reference - timedelta(days=retention_days)
        for backup in backups:
            created = parse_datetime(backup.created_at)
            if created is None or created >= cutoff:
                keep.add(backup.id)
    return [b for b in backups if b.id not in keep]


def apply_retention(schedule, user=None):
    """Apply a schedule's retention policy to that connection's scheduled backups."""
    candidates = backup_repository.list_successful_for_connection(schedule.connection_id, kind="scheduled")
    doomed = select_backups_to_delete(
        candidates, schedule.retention_days, schedule.keep_daily,
        schedule.keep_weekly, schedule.keep_monthly)
    for backup in doomed:
        delete_backup(backup, user)
    if doomed:
        log.info("Retention removed %d backup(s) for connection %s", len(doomed), schedule.connection_id)
    return len(doomed)


def apply_retention_all(user=None):
    return sum(apply_retention(s, user) for s in schedule_repository.list_schedules())
