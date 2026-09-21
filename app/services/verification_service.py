"""Backup integrity verification (SHA-256 and optional deep check)."""
import logging
import tempfile
from pathlib import Path

from flask import current_app

from ..exceptions import DBSafeError
from ..repositories import backup_repository, log_repository
from ..utils.datetime_utils import now_str
from ..utils.file_utils import is_within
from ..utils.hash_utils import digests_equal, sha256_file
from . import compression_service, encryption_service

log = logging.getLogger("dbsafe.backup")


def resolve_backup_path(backup):
    """Path of the backup file, or None when it is missing or outside the allowed roots."""
    if not backup.file_path:
        return None
    path = Path(backup.file_path)
    if not is_within(path, current_app.config["ALLOWED_BACKUP_ROOTS"]):
        return None
    return path if path.is_file() else None


def _deep_check(backup, path):
    """Decrypt / decompress into a temporary area to prove the file is readable."""
    with tempfile.TemporaryDirectory(dir=current_app.config["TEMP_DIR"]) as tmp:
        current = path
        if backup.encryption_enabled:
            decrypted = Path(tmp) / "decrypted"
            encryption_service.decrypt_file(current, decrypted, encryption_service.get_backup_key())
            current = decrypted
        if backup.compression_type != "none":
            compression_service.test_integrity(current, backup.compression_type)


def verify_backup(backup, deep=False, persist=True, user=None):
    """Verify *backup*. Returns a dict with ``status`` = valid | invalid | missing."""
    path = resolve_backup_path(backup)
    if path is None:
        result = {"status": "missing", "message": "The backup file is missing or not accessible.",
                  "checksum_expected": backup.checksum, "checksum_actual": None}
    else:
        actual = sha256_file(path)
        if not digests_equal(actual, backup.checksum):
            result = {"status": "invalid",
                      "message": "Integrity verification failed. The backup may be corrupted or modified.",
                      "checksum_expected": backup.checksum, "checksum_actual": actual}
        else:
            result = {"status": "valid", "message": "Checksum matches.",
                      "checksum_expected": backup.checksum, "checksum_actual": actual}
            if deep:
                try:
                    _deep_check(backup, path)
                    result["message"] = "Checksum matches and the file can be decrypted/decompressed."
                except DBSafeError as exc:
                    result.update(status="invalid", message=f"Deep verification failed: {exc.message}")
    result["deep"] = bool(deep)
    result["backup_id"] = backup.backup_id

    if persist:
        backup_repository.update(backup.id, verification_status=result["status"],
                                 last_verified_at=now_str())
        log_repository.add("verify_backup", "success" if result["status"] == "valid" else "failed",
                           f"{backup.backup_id}: {result['message']}", backup.database_name, user)
    log.info("Verification of %s: %s", backup.backup_id, result["status"])
    return result
