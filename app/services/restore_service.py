"""Restore workflow: verify -> safety backup -> decrypt -> decompress -> restore -> verify."""
import logging
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from flask import current_app

from ..exceptions import DBSafeError, NotFoundError, RestoreError, ValidationError
from ..repositories import backup_repository, log_repository, restore_repository
from ..utils.datetime_utils import duration_str, now_str
from . import (backup_service, compression_service, connection_service, encryption_service,
               notification_service, verification_service)

log = logging.getLogger("dbsafe.restore")


@dataclass
class RestoreOptions:
    backup_pk: int
    connection_id: int
    target_database: str
    safety_backup: bool = True
    user: Optional[dict] = None


def prepare_restore(backup_pk, connection_id, target_database, safety_backup=True, user=None):
    """Validate the request and create the 'running' restore row. Returns (row, options)."""
    backup = backup_repository.get(backup_pk)
    if backup is None:
        raise NotFoundError("Backup not found")
    if backup.status != "success":
        raise ValidationError("Only successful backups can be restored")
    connection = connection_service.get_connection(connection_id)
    if connection.database_type != backup.database_type:
        raise ValidationError(
            f"This is a {backup.database_type} backup and cannot be restored into a "
            f"{connection.database_type} connection")
    target = connection_service.validate_target_database(connection, target_database)

    restore_id = restore_repository.create({
        "backup_id": backup.id, "backup_code": backup.backup_id,
        "connection_id": connection.id, "connection_name": connection.name,
        "target_database": target, "status": "running", "started_at": now_str(),
        "initiated_by": (user or {}).get("username") or "system",
    })
    log.info("Restore %s of %s into '%s' (%s) started", restore_id, backup.backup_id,
             connection.name, target)
    options = RestoreOptions(backup.id, connection.id, target, bool(safety_backup), user)
    return restore_repository.get(restore_id), options


def execute_restore(restore_pk, options):
    """Run the restore. Never raises; the outcome is stored on the restore row."""
    restore = restore_repository.get(restore_pk)
    started = time.monotonic()
    steps = []
    safety_code = None
    try:
        cfg = current_app.config
        backup = backup_repository.get(options.backup_pk)
        if backup is None:
            raise RestoreError("The backup no longer exists")
        connection = connection_service.get_connection(options.connection_id)
        path = verification_service.resolve_backup_path(backup)
        if path is None:
            raise RestoreError("The backup file is missing or not accessible")

        # 1. Integrity
        result = verification_service.verify_backup(backup, deep=False, user=options.user)
        if result["status"] != "valid":
            raise RestoreError(f"Backup integrity check failed: {result['message']}")
        steps.append({"step": "Verify backup checksum", "status": "ok"})

        adapter = connection_service.build_adapter(connection, options.target_database)

        # 2. Safety backup of what is about to be overwritten
        if options.safety_backup:
            if adapter.database_exists():
                safety_options = backup_service.BackupOptions(
                    compression="gzip", encryption=bool(backup.encryption_enabled), verify=True,
                    kind="safety", database_override=options.target_database, user=options.user)
                pending = backup_service.prepare_backup(connection.id, safety_options)
                safety = backup_service.execute_backup(pending.id, safety_options)
                if safety.status != "success":
                    raise RestoreError(f"Safety backup failed, restore aborted: {safety.error_message}")
                safety_code = safety.backup_id
                restore_repository.update(restore_pk, safety_backup_code=safety_code)
                steps.append({"step": "Create safety backup", "status": "ok", "detail": safety_code})
            else:
                steps.append({"step": "Create safety backup", "status": "skipped",
                              "detail": "Target database does not exist yet"})

        # 3-5. Decrypt, decompress, restore
        with tempfile.TemporaryDirectory(dir=cfg["TEMP_DIR"]) as tmp:
            current = path
            if backup.encryption_enabled:
                decrypted = Path(tmp) / "decrypted"
                encryption_service.decrypt_file(current, decrypted, encryption_service.get_backup_key())
                current = decrypted
                steps.append({"step": "Decrypt backup", "status": "ok"})
            if backup.compression_type != "none":
                raw = Path(tmp) / "restore_payload"
                compression_service.decompress_file(current, raw, backup.compression_type)
                current = raw
                steps.append({"step": "Decompress backup", "status": "ok"})
            try:
                adapter.restore_backup(current, source_database=backup.database_name)
            finally:
                adapter.disconnect()
        steps.append({"step": "Restore database", "status": "ok"})

        # 6. Verify the result
        verification = adapter.verify_restore(expected_tables=backup.table_list() or None)
        adapter.disconnect()
        steps.append({"step": "Verify restored database",
                      "status": "ok" if verification.get("ok") else "failed",
                      "detail": verification.get("message")})
        if not verification.get("ok"):
            raise RestoreError(f"Restore verification failed: {verification.get('message')}")

        duration = round(time.monotonic() - started, 2)
        restore_repository.update(
            restore_pk, status="success", completed_at=now_str(), duration_seconds=duration,
            verification_result={"steps": steps, "verification": verification}, error_message=None)
        message = (f"Restore of {backup.backup_id} into '{connection.name}' "
                   f"({options.target_database}) completed in {duration_str(duration)}")
        log.info(message)
        log_repository.add("restore", "success", message, options.target_database, options.user)
        notification_service.notify("restore_success", f"Restore successful: {connection.name}", message)
    except Exception as exc:
        reason = exc.message if isinstance(exc, DBSafeError) else f"Unexpected error: {exc}"
        if isinstance(exc, DBSafeError):
            log.error("Restore %s failed: %s", restore_pk, reason)
        else:
            log.exception("Restore %s failed unexpectedly", restore_pk)
        steps.append({"step": "Restore failed", "status": "failed", "detail": reason})
        restore_repository.update(
            restore_pk, status="failed", completed_at=now_str(), error_message=reason[:1500],
            duration_seconds=round(time.monotonic() - started, 2),
            verification_result={"steps": steps}, safety_backup_code=safety_code)
        log_repository.add("restore", "failed", f"Restore {restore_pk}: {reason}",
                           restore.target_database, options.user)
        notification_service.notify("restore_failed", "Restore failed",
                                    f"Target: {restore.target_database}\nReason: {reason}")
    return restore_repository.get(restore_pk)
