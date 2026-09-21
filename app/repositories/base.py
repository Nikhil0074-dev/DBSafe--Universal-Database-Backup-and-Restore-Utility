"""Low-level access to the application metadata database (SQLite).

Every call opens its own short-lived connection, which keeps the code safe to
use from Flask requests, the scheduler and background worker threads.
"""
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app

log = logging.getLogger("dbsafe")


def _connect():
    conn = sqlite3.connect(str(current_app.config["DATABASE_PATH"]), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(sql, params=()):
    with session() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def fetch_one(sql, params=()):
    with session() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def execute(sql, params=()):
    """Run a write statement; returns ``lastrowid``."""
    with session() as conn:
        return conn.execute(sql, params).lastrowid


def execute_count(sql, params=()):
    """Run a write statement; returns the number of affected rows."""
    with session() as conn:
        return conn.execute(sql, params).rowcount


def update_row(table, row_id, fields, allowed):
    """UPDATE selected columns. *table* and *allowed* are trusted constants."""
    columns = [key for key in fields if key in allowed]
    if not columns:
        return
    assignments = ", ".join(f"{column} = ?" for column in columns)
    execute(f"UPDATE {table} SET {assignments} WHERE id = ?",
            [fields[column] for column in columns] + [row_id])


def init_database():
    """Create tables, the default administrator, and clean up interrupted jobs."""
    from . import backup_repository, restore_repository, user_repository
    from werkzeug.security import generate_password_hash

    path = Path(current_app.config["DATABASE_PATH"])
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = Path(current_app.config["SCHEMA_PATH"]).read_text(encoding="utf-8")
    conn = sqlite3.connect(str(path), timeout=30)
    try:
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error:  # pragma: no cover - unsupported filesystem
            pass
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()

    if user_repository.count() == 0:
        username = current_app.config["ADMIN_USERNAME"]
        password = current_app.config["ADMIN_PASSWORD"]
        user_repository.create(username, generate_password_hash(password, method="pbkdf2:sha256"), "admin")
        log.warning("Default administrator '%s' created. Change its password after the first login.",
                    username)

    interrupted = backup_repository.mark_running_as_failed()
    interrupted += restore_repository.mark_running_as_failed()
    if interrupted:
        log.warning("%d operation(s) were interrupted by a restart and marked as failed", interrupted)
