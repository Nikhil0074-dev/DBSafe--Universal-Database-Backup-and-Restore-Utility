"""Application-specific exceptions. Every one maps to an HTTP status code."""


class DBSafeError(Exception):
    status_code = 400

    def __init__(self, message="", status_code=None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.details = details

    def __str__(self):
        return self.message


class ValidationError(DBSafeError):
    status_code = 400


class AuthenticationError(DBSafeError):
    status_code = 401


class PermissionDenied(DBSafeError):
    status_code = 403


class NotFoundError(DBSafeError):
    status_code = 404


class ConflictError(DBSafeError):
    status_code = 409


class TooManyAttempts(DBSafeError):
    status_code = 429


class AdapterError(DBSafeError):
    """A database adapter could not perform an operation."""
    status_code = 502


class CommandError(DBSafeError):
    """An external command (mysqldump, pg_dump, ...) failed."""
    status_code = 500


class EncryptionError(DBSafeError):
    status_code = 500


class BackupError(DBSafeError):
    status_code = 500


class RestoreError(DBSafeError):
    status_code = 500


class VerificationError(DBSafeError):
    status_code = 500
