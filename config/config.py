"""Configuration for DBSafe.

Every setting can be overridden with an environment variable (see .env.example)
or, for tests, through the ``overrides`` argument of :func:`build_config`.
"""
import os
import secrets
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

try:  # python-dotenv is optional
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover
    pass


def _env(name, default=None):
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def _env_bool(name, default=False):
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name, default):
    try:
        return int(_env(name, default))
    except (TypeError, ValueError):
        return default


def _load_secret(path, nbytes=32):
    """Return the secret stored in *path*, creating it on first use."""
    path = Path(path)
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(nbytes)
    path.write_text(value, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - e.g. Windows
        pass
    return value


_PATH_KEYS = ("ROOT_DIR", "INSTANCE_DIR", "DATABASE_PATH", "SCHEMA_PATH",
              "BACKUP_DIR", "TEMP_DIR", "LOG_DIR")


def build_config(overrides=None):
    """Build the configuration dictionary used by ``create_app``."""
    overrides = dict(overrides or {})
    root = Path(overrides.get("ROOT_DIR") or _env("DBSAFE_HOME") or BASE_DIR).resolve()
    instance_dir = root / "instance"

    cfg = {
        # Paths
        "ROOT_DIR": root,
        "INSTANCE_DIR": instance_dir,
        "DATABASE_PATH": root / "database" / "dbsafe.db",
        "SCHEMA_PATH": BASE_DIR / "database" / "schema.sql",
        "BACKUP_DIR": root / "backups",
        "TEMP_DIR": instance_dir / "tmp",
        "LOG_DIR": root / "logs",
        # Logging
        "LOG_LEVEL": _env("DBSAFE_LOG_LEVEL", "INFO"),
        "LOG_TO_CONSOLE": True,
        # Secrets
        "SECRET_KEY": _env("DBSAFE_SECRET_KEY"),
        "ENCRYPTION_KEY": _env("DBSAFE_ENCRYPTION_KEY"),
        # Sessions / web
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": _env_bool("DBSAFE_SESSION_COOKIE_SECURE", False),
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=8),
        "MAX_CONTENT_LENGTH": 1024 * 1024,
        "JSON_SORT_KEYS": False,
        "LOGIN_MAX_ATTEMPTS": _env_int("DBSAFE_LOGIN_MAX_ATTEMPTS", 5),
        "LOGIN_WINDOW_SECONDS": _env_int("DBSAFE_LOGIN_WINDOW_SECONDS", 300),
        # First administrator
        "ADMIN_USERNAME": _env("DBSAFE_ADMIN_USERNAME", "admin"),
        "ADMIN_PASSWORD": _env("DBSAFE_ADMIN_PASSWORD", "Admin@123"),
        # Backup behaviour
        "MAX_BACKUP_SIZE_MB": _env_int("DBSAFE_MAX_BACKUP_SIZE_MB", 0),  # 0 = unlimited
        "MIN_FREE_MB": _env_int("DBSAFE_MIN_FREE_MB", 50),
        "STORAGE_CAPACITY_GB": _env_int("DBSAFE_STORAGE_CAPACITY_GB", 0),  # 0 = use disk size
        "STORAGE_WARN_PERCENT": _env_int("DBSAFE_STORAGE_WARN_PERCENT", 90),
        "COMMAND_TIMEOUT_SECONDS": _env_int("DBSAFE_COMMAND_TIMEOUT", 6 * 3600),
        "WORKER_THREADS": _env_int("DBSAFE_WORKER_THREADS", 4),
        # Scheduler
        "SCHEDULER_ENABLED": _env_bool("DBSAFE_SCHEDULER_ENABLED", True),
        # External tools
        "MYSQLDUMP_PATH": _env("MYSQLDUMP_PATH"),
        "MYSQL_PATH": _env("MYSQL_PATH"),
        "MYSQLDUMP_EXTRA_ARGS": _env("MYSQLDUMP_EXTRA_ARGS", ""),
        "PG_DUMP_PATH": _env("PG_DUMP_PATH"),
        "PSQL_PATH": _env("PSQL_PATH"),
        "MONGODUMP_PATH": _env("MONGODUMP_PATH"),
        "MONGORESTORE_PATH": _env("MONGORESTORE_PATH"),
        # Notifications
        "SMTP_HOST": _env("DBSAFE_SMTP_HOST"),
        "SMTP_PORT": _env_int("DBSAFE_SMTP_PORT", 587),
        "SMTP_USER": _env("DBSAFE_SMTP_USER"),
        "SMTP_PASSWORD": _env("DBSAFE_SMTP_PASSWORD"),
        "SMTP_USE_TLS": _env_bool("DBSAFE_SMTP_USE_TLS", True),
        "NOTIFY_FROM": _env("DBSAFE_NOTIFY_FROM", "dbsafe@localhost"),
        "NOTIFY_TO": _env("DBSAFE_NOTIFY_TO", ""),
    }
    cfg.update(overrides)

    for key in _PATH_KEYS:
        cfg[key] = Path(cfg[key])

    if not cfg.get("SECRET_KEY"):
        cfg["SECRET_KEY"] = _load_secret(cfg["INSTANCE_DIR"] / "secret.key")
    if not cfg.get("ENCRYPTION_KEY"):
        cfg["ENCRYPTION_KEY"] = _load_secret(cfg["INSTANCE_DIR"] / "encryption.key")

    if "ALLOWED_BACKUP_ROOTS" in overrides:
        roots = [Path(p) for p in overrides["ALLOWED_BACKUP_ROOTS"]]
    else:
        extra = _env("DBSAFE_ALLOWED_BACKUP_ROOTS", "")
        roots = [Path(p) for p in extra.split(os.pathsep) if p.strip()]
    if cfg["BACKUP_DIR"] not in roots:
        roots.insert(0, cfg["BACKUP_DIR"])
    cfg["ALLOWED_BACKUP_ROOTS"] = roots
    return cfg
