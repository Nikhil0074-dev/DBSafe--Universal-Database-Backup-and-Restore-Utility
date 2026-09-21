"""Input validation for every API payload."""
import re
from pathlib import Path

from ..exceptions import ValidationError

DB_TYPES = ("mysql", "postgresql", "sqlite", "mongodb")
DEFAULT_PORTS = {"mysql": 3306, "postgresql": 5432, "mongodb": 27017, "sqlite": None}
COMPRESSIONS = ("none", "gzip", "zip")
BACKUP_TYPES = ("full", "selective")
FREQUENCIES = ("hourly", "every_6_hours", "daily", "weekly", "monthly", "custom")
ROLES = ("admin", "operator")

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_$\-]{1,64}$")
_TABLE = re.compile(r"^[A-Za-z0-9_$.\-]{1,128}$")
_USERNAME = re.compile(r"^[A-Za-z0-9_.@\-]{3,64}$")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def clean_str(data, key, *, required=True, max_len=255, default=None):
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"'{key}' is required")
        return default
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValidationError(f"'{key}' must be text")
    text = str(value).strip()
    if len(text) > max_len:
        raise ValidationError(f"'{key}' must be at most {max_len} characters")
    if "\x00" in text:
        raise ValidationError(f"'{key}' contains invalid characters")
    return text


def clean_int(data, key, *, required=False, default=None, minimum=None, maximum=None):
    value = data.get(key)
    if value is None or value == "":
        if required:
            raise ValidationError(f"'{key}' is required")
        return default
    if isinstance(value, bool):
        raise ValidationError(f"'{key}' must be a number")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"'{key}' must be a number") from None
    if minimum is not None and number < minimum:
        raise ValidationError(f"'{key}' must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise ValidationError(f"'{key}' must be at most {maximum}")
    return number


def clean_bool(data, key, default=False):
    value = data.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "1", "yes", "on"):
        return True
    if isinstance(value, str) and value.strip().lower() in ("false", "0", "no", "off"):
        return False
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise ValidationError(f"'{key}' must be true or false")


def is_safe_identifier(value):
    return bool(value) and bool(_IDENTIFIER.match(str(value)))


def validate_identifier(value, label="name"):
    if not is_safe_identifier(value):
        raise ValidationError(
            f"Invalid {label}: use only letters, digits, '_', '$' or '-' (max 64 characters)"
        )
    return value


def validate_table_names(tables):
    if tables is None:
        return []
    if not isinstance(tables, (list, tuple)):
        raise ValidationError("'tables' must be a list")
    cleaned = []
    for table in tables:
        if not isinstance(table, str) or not _TABLE.match(table):
            raise ValidationError(f"Invalid table name: {table!r}")
        if table not in cleaned:
            cleaned.append(table)
    return cleaned


def validate_password(password):
    if not isinstance(password, str) or len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long")
    if len(password) > 128:
        raise ValidationError("Password must be at most 128 characters long")
    if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)):
        raise ValidationError("Password must contain at least one letter and one digit")
    return password


def validate_username(username):
    if not isinstance(username, str) or not _USERNAME.match(username.strip()):
        raise ValidationError(
            "Username must be 3-64 characters (letters, digits, '.', '_', '-', '@')"
        )
    return username.strip()


def validate_role(role):
    if role not in ROLES:
        raise ValidationError(f"Role must be one of: {', '.join(ROLES)}")
    return role


def validate_connection_payload(data):
    """Validate a database-connection payload. ``password`` is None when not supplied."""
    db_type = clean_str(data, "database_type", max_len=20).lower()
    if db_type not in DB_TYPES:
        raise ValidationError(f"Unsupported database type. Choose one of: {', '.join(DB_TYPES)}")
    name = clean_str(data, "name", max_len=100)

    if db_type == "sqlite":
        raw = clean_str(data, "database_name", max_len=1024)
        return {
            "name": name, "database_type": db_type, "host": None, "port": None,
            "username": None, "password": None, "extra": {},
            "database_name": str(Path(raw).expanduser().resolve()),
        }

    host = clean_str(data, "host", required=False, default="localhost", max_len=255)
    if not re.match(r"^[A-Za-z0-9_.\-:]+$", host):
        raise ValidationError("Invalid host name")
    port = clean_int(data, "port", default=DEFAULT_PORTS[db_type], minimum=1, maximum=65535)
    username = clean_str(data, "username", required=db_type != "mongodb", max_len=128)
    password = data.get("password")
    if password is not None and not isinstance(password, str):
        raise ValidationError("'password' must be text")
    if password is not None and len(password) > 512:
        raise ValidationError("'password' is too long")
    database_name = validate_identifier(clean_str(data, "database_name", max_len=64), "database name")

    extra = {}
    raw_extra = data.get("extra") or {}
    if not isinstance(raw_extra, dict):
        raise ValidationError("'extra' must be an object")
    if db_type == "mongodb" and raw_extra.get("auth_source"):
        extra["auth_source"] = validate_identifier(str(raw_extra["auth_source"]), "authentication database")

    return {
        "name": name, "database_type": db_type, "host": host, "port": port,
        "username": username, "password": password or None, "database_name": database_name,
        "extra": extra,
    }


def _validate_destination(data):
    return clean_str(data, "destination", required=False, max_len=1024)


def validate_backup_payload(data):
    backup_type = clean_str(data, "backup_type", required=False, default="full", max_len=20).lower()
    if backup_type not in BACKUP_TYPES:
        raise ValidationError("backup_type must be 'full' or 'selective'")
    tables = validate_table_names(data.get("tables"))
    if backup_type == "selective" and not tables:
        raise ValidationError("Select at least one table for a selective backup")
    if backup_type == "full":
        tables = []
    compression = clean_str(data, "compression", required=False, default="gzip", max_len=10).lower()
    if compression not in COMPRESSIONS:
        raise ValidationError(f"compression must be one of: {', '.join(COMPRESSIONS)}")
    return {
        "connection_id": clean_int(data, "connection_id", required=True, minimum=1),
        "backup_type": backup_type,
        "tables": tables,
        "compression": compression,
        "encryption": clean_bool(data, "encryption", False),
        "verify": clean_bool(data, "verify", True),
        "destination": _validate_destination(data),
        "sync": clean_bool(data, "sync", False),
    }


def validate_restore_payload(data):
    if not clean_bool(data, "confirm", False):
        raise ValidationError("The restore must be confirmed (confirm: true)")
    return {
        "backup_id": clean_int(data, "backup_id", required=True, minimum=1),
        "connection_id": clean_int(data, "connection_id", required=True, minimum=1),
        "target_database": clean_str(data, "target_database", required=False, max_len=1024),
        "safety_backup": clean_bool(data, "safety_backup", True),
        "sync": clean_bool(data, "sync", False),
    }


def validate_cron_expression(expression):
    try:
        from apscheduler.triggers.cron import CronTrigger

        CronTrigger.from_crontab(expression)
    except Exception:
        raise ValidationError(
            "Invalid cron expression. Use 5 fields: minute hour day month day-of-week"
        ) from None
    return expression


def validate_schedule_payload(data):
    frequency = clean_str(data, "frequency", max_len=20).lower()
    if frequency not in FREQUENCIES:
        raise ValidationError(f"frequency must be one of: {', '.join(FREQUENCIES)}")
    schedule_time = clean_str(data, "schedule_time", required=False, default="02:00", max_len=5)
    if not _TIME.match(schedule_time):
        raise ValidationError("schedule_time must be in HH:MM (24-hour) format")
    cron_expression = clean_str(data, "cron_expression", required=False, max_len=100)
    if frequency == "custom":
        if not cron_expression:
            raise ValidationError("A cron expression is required for a custom schedule")
        validate_cron_expression(cron_expression)
    payload = validate_backup_payload(data)
    payload.pop("sync", None)
    payload.update({
        "name": clean_str(data, "name", required=False, max_len=100),
        "frequency": frequency,
        "schedule_time": schedule_time,
        "day_of_week": clean_int(data, "day_of_week", default=0, minimum=0, maximum=6),
        "day_of_month": clean_int(data, "day_of_month", default=1, minimum=1, maximum=28),
        "cron_expression": cron_expression if frequency == "custom" else None,
        "retention_days": clean_int(data, "retention_days", default=30, minimum=0, maximum=3650),
        "keep_daily": clean_int(data, "keep_daily", default=0, minimum=0, maximum=365),
        "keep_weekly": clean_int(data, "keep_weekly", default=0, minimum=0, maximum=520),
        "keep_monthly": clean_int(data, "keep_monthly", default=0, minimum=0, maximum=120),
        "enabled": clean_bool(data, "enabled", True),
    })
    return payload
