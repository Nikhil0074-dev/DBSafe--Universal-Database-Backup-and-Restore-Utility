"""Backup workflow: adapter -> compress -> encrypt -> checksum -> store -> verify."""
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from flask import current_app

from ..exceptions import BackupError, DBSafeError, NotFoundError, ValidationError
from ..repositories import backup_repository, log_repository
from ..utils.datetime_utils import duration_str, filename_timestamp, now_str
from ..utils.file_utils import remove_quietly, safe_filename, unique_path
from ..utils.hash_utils import sha256_file
from ..utils.validation import BACKUP_TYPES, COMPRESSIONS
from . import (compression_service, connection_service, encryption_service, notification_service,
               storage_service, verification_service)

log = logging.getLogger("dbsafe.backup")


@dataclass
class BackupOptions:
    backup_type: str = "full"
    tables: list = field(default_factory=list)
    compression: str = "gzip"
    encryption: bool = False
    verify: bool = True
    destination: Optional[str] = None
    kind: str = "manual"                       # manual | scheduled | safety
    database_override: Optional[str] = None    # back up a different database of the same server
    user: Optional[dict] = None


def _username(user):
    return (user or {}).get("username") or "scheduler"


def _label(connection, database_name):
    if connection.database_type == "sqlite":
        return safe_filename(Path(database_name).stem)
    return safe_filename(database_name)


def prepare_backup(connection_id, options):
    """Validate the request and create the 'running' metadata row."""
    connection = connection_service.get_connection(connection_id)
    if options.backup_type not in BACKUP_TYPES:
        raise ValidationError("Invalid backup type")
    if options.compression not in COMPRESSIONS:
        raise ValidationError("Invalid compression method")
    if options.backup_type == "selective" and not options.tables:
        raise ValidationError("Select at least one table for a selective backup")
    if options.encryption:
        encryption_service.validate_key(encryption_service.get_backup_key())
    if options.destination:  # fail fast on a bad destination
        storage_service.resolve_destination(connection.database_type, options.destination)

    database_name = options.database_override or connection.database_name
    row_id = backup_repository.create({
        "backup_id": f"PENDING-{time.time_ns()}",
        "connection_id": connection.id,
        "connection_name": connection.name,
        "database_type": connection.database_type,
        "database_name": database_name,
        "backup_type": options.backup_type,
        "kind": options.kind,
        "tables": list(options.tables or []),
        "compression_type": options.compression,
        "compression_enabled": 1 if options.compression != "none" else 0,
        "encryption_enabled": 1 if options.encryption else 0,
        "status": "running",
        "created_by": _username(options.user),
        "created_at": now_str(),
    })
    code = f"BK-{time.strftime('%Y%m%d')}-{row_id:05d}"
    backup_repository.update(row_id, backup_id=code)
    log.info("Backup %s started for '%s' (%s)", code, connection.name, options.backup_type)
    return backup_repository.get(row_id)


def execute_backup(backup_pk, options):
    """Run the backup pipeline. Never raises; the outcome is stored on the backup row."""
    backup = backup_repository.get(backup_pk)
    started = time.monotonic()
    final_path = None
    try:
        cfg = current_app.config
        connection = connection_service.get_connection(backup.connection_id)
        adapter = connection_service.build_adapter(connection, options.database_override)
        dest_dir = storage_service.resolve_destination(connection.database_type, options.destination)
        storage_service.ensure_free_space(dest_dir)

        base = f"{_label(connection, adapter.database)}_{filename_timestamp()}"
        with tempfile.TemporaryDirectory(dir=cfg["TEMP_DIR"]) as tmp:
            tmp_dir = Path(tmp)
            tables = list(options.tables or [])
            snapshot = tables or _table_snapshot(adapter)

            raw = tmp_dir / f"{base}{adapter.backup_extension}"
            try:
                adapter.create_backup(raw, tables=tables or None)
            finally:
                adapter.disconnect()
            if not raw.is_file():
                raise BackupError("The database tool did not create a backup file")
            original_size = raw.stat().st_size
            limit_mb = int(cfg.get("MAX_BACKUP_SIZE_MB") or 0)
            if limit_mb and original_size > limit_mb * 1024 * 1024:
                raise BackupError(f"The backup ({original_size // (1024 * 1024)} MB) exceeds the "
                                  f"configured maximum of {limit_mb} MB")

            current, name = raw, raw.name
            if options.compression != "none":
                name += compression_service.extension(options.compression)
                compressed = tmp_dir / name
                compression_service.compress_file(current, compressed, options.compression)
                remove_quietly(current)
                current = compressed
            compressed_size = current.stat().st_size

            if options.encryption:
                name += ".enc"
                encrypted = tmp_dir / name
                encryption_service.encrypt_file(current, encrypted, encryption_service.get_backup_key())
                remove_quietly(current)
                current = encrypted
            stored_size = current.stat().st_size
            checksum = sha256_file(current)

            final_path = unique_path(dest_dir / name)
            partial = final_path.with_name(final_path.name + ".part")
            shutil.move(str(current), str(partial))
            os.replace(partial, final_path)
            try:
                os.chmod(final_path, 0o600)
            except OSError:  # pragma: no cover - e.g. Windows
                pass

        duration = round(time.monotonic() - started, 2)
        backup_repository.update(
            backup.id, file_path=str(final_path), file_name=final_path.name,
            original_size=original_size, compressed_size=compressed_size, stored_size=stored_size,
            checksum=checksum, tables=json.dumps(snapshot), status="success",
            duration_seconds=duration, error_message=None)
        backup = backup_repository.get(backup.id)

        if options.verify:
            result = verification_service.verify_backup(backup, deep=True, user=options.user)
            if result["status"] != "valid":
                raise BackupError(f"Backup verification failed: {result['message']}")
        else:
            backup_repository.update(backup.id, verification_status="not_verified")

        message = (f"{backup.backup_id} for '{backup.connection_name}' completed in "
                   f"{duration_str(duration)} ({stored_size} bytes)")
        log.info(message)
        log_repository.add("backup", "success", message, backup.database_name, options.user or {})
        notification_service.notify(
            "backup_success", f"Backup successful: {backup.connection_name}",
            f"Backup {backup.backup_id}\nDatabase: {backup.database_name}\nSize: {stored_size} bytes\n"
            f"Duration: {duration_str(duration)}")
    except Exception as exc:
        reason = exc.message if isinstance(exc, DBSafeError) else f"Unexpected error: {exc}"
        if isinstance(exc, DBSafeError):
            log.error("Backup %s failed: %s", backup.backup_id, reason)
        else:
            log.exception("Backup %s failed unexpectedly", backup.backup_id)
        if final_path is not None and "verification failed" in reason.lower():
            pass  # keep the file for inspection; the row is marked failed below
        elif final_path is not None:
            remove_quietly(final_path)
        backup_repository.update(
            backup.id, status="failed", error_message=reason[:1500],
            duration_seconds=round(time.monotonic() - started, 2))
        log_repository.add("backup", "failed", f"{backup.backup_id}: {reason}",
                           backup.database_name, options.user or {})
        notification_service.notify(
            "backup_failed", f"Backup failed: {backup.connection_name}",
            f"Backup {backup.backup_id}\nDatabase: {backup.database_name}\nReason: {reason}")
    return backup_repository.get(backup.id)


def _table_snapshot(adapter):
    """Table names at backup time (used later to verify restores). Best effort."""
    try:
        return adapter.get_tables()
    except Exception:
        return []


def get_backup(identifier):
    """Look a backup up by numeric id or by code such as BK-20260920-00001."""
    text = str(identifier)
    backup = backup_repository.get(int(text)) if text.isdigit() else backup_repository.get_by_code(text)
    if backup is None:
        raise NotFoundError("Backup not found")
    return backup
