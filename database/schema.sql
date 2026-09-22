-- DBSafe application metadata schema (SQLite)

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'operator')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS database_connections (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT NOT NULL UNIQUE COLLATE NOCASE,
    database_type        TEXT NOT NULL CHECK (database_type IN ('mysql', 'postgresql', 'sqlite', 'mongodb')),
    host                 TEXT,
    port                 INTEGER,
    username             TEXT,
    database_name        TEXT NOT NULL,
    credential_reference TEXT,          -- encrypted password (Fernet token)
    extra                TEXT,          -- JSON, e.g. {"auth_source": "admin"}
    created_at           TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS backups (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_id           TEXT NOT NULL UNIQUE,          -- e.g. BK-20260920-00001
    connection_id       INTEGER REFERENCES database_connections(id) ON DELETE SET NULL,
    connection_name     TEXT,
    database_type       TEXT,
    database_name       TEXT,
    backup_type         TEXT NOT NULL DEFAULT 'full',  -- full | selective
    kind                TEXT NOT NULL DEFAULT 'manual',-- manual | scheduled | safety
    tables              TEXT,                          -- JSON list
    file_path           TEXT,
    file_name           TEXT,
    original_size       INTEGER NOT NULL DEFAULT 0,
    compressed_size     INTEGER NOT NULL DEFAULT 0,    -- size after compression (before encryption)
    stored_size         INTEGER NOT NULL DEFAULT 0,    -- final size on disk
    compression_type    TEXT NOT NULL DEFAULT 'none',
    compression_enabled INTEGER NOT NULL DEFAULT 0,
    encryption_enabled  INTEGER NOT NULL DEFAULT 0,
    checksum            TEXT,
    status              TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed')),
    verification_status TEXT NOT NULL DEFAULT 'not_verified',
    last_verified_at    TEXT,
    duration_seconds    REAL NOT NULL DEFAULT 0,
    error_message       TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_backups_connection ON backups(connection_id);
CREATE INDEX IF NOT EXISTS idx_backups_status ON backups(status);
CREATE INDEX IF NOT EXISTS idx_backups_created ON backups(created_at);

CREATE TABLE IF NOT EXISTS schedules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id   INTEGER NOT NULL REFERENCES database_connections(id) ON DELETE CASCADE,
    name            TEXT,
    frequency       TEXT NOT NULL,
    schedule_time   TEXT NOT NULL DEFAULT '02:00',
    day_of_week     INTEGER NOT NULL DEFAULT 0,
    day_of_month    INTEGER NOT NULL DEFAULT 1,
    cron_expression TEXT,
    backup_type     TEXT NOT NULL DEFAULT 'full',
    tables          TEXT,
    compression     TEXT NOT NULL DEFAULT 'gzip',
    encryption      INTEGER NOT NULL DEFAULT 0,
    verify          INTEGER NOT NULL DEFAULT 1,
    destination     TEXT,
    retention_days  INTEGER NOT NULL DEFAULT 30,
    keep_daily      INTEGER NOT NULL DEFAULT 0,
    keep_weekly     INTEGER NOT NULL DEFAULT 0,
    keep_monthly    INTEGER NOT NULL DEFAULT 0,
    enabled         INTEGER NOT NULL DEFAULT 1,
    last_run_at     TEXT,
    last_status     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS restore_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_id           INTEGER REFERENCES backups(id) ON DELETE SET NULL,
    backup_code         TEXT,
    connection_id       INTEGER REFERENCES database_connections(id) ON DELETE SET NULL,
    connection_name     TEXT,
    target_database     TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed')),
    safety_backup_code  TEXT,
    verification_result TEXT,           -- JSON
    started_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    completed_at        TEXT,
    duration_seconds    REAL NOT NULL DEFAULT 0,
    error_message       TEXT,
    initiated_by        TEXT
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER,
    username      TEXT,
    operation     TEXT NOT NULL,
    database_name TEXT,
    status        TEXT NOT NULL,
    message       TEXT,
    timestamp     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON operation_logs(timestamp);
