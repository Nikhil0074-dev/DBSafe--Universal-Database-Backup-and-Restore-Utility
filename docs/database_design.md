# Metadata database design (SQLite, `database/schema.sql`)

* **users**(id, username, password_hash, role[admin|operator], created_at)
* **database_connections**(id, name, database_type, host, port, username, database_name,
  credential_reference *(Fernet-encrypted password)*, extra *(JSON)*, created_at)
* **backups**(id, backup_id `BK-YYYYMMDD-NNNNN`, connection_id → connections *(SET NULL on delete)*, connection_name,
  database_type, database_name, backup_type, kind[manual|scheduled|safety], tables *(JSON)*, file_path, file_name,
  original_size, compressed_size, stored_size, compression_type, compression_enabled, encryption_enabled,
  checksum, status[running|success|failed], verification_status, last_verified_at, duration_seconds,
  error_message, created_by, created_at)
* **schedules**(id, connection_id *(CASCADE)*, frequency, schedule_time, day_of_week, day_of_month, cron_expression,
  backup_type, tables, compression, encryption, verify, destination, retention_days, keep_daily, keep_weekly,
  keep_monthly, enabled, last_run_at, last_status)
* **restore_logs**(id, backup_id → backups, backup_code, connection_id, connection_name, target_database, status,
  safety_backup_code, verification_result *(JSON)*, started_at, completed_at, duration_seconds, error_message,
  initiated_by)
* **operation_logs**(id, user_id, username, operation, database_name, status, message, timestamp)

Relationships: connection 1—N backups, connection 1—N schedules, backup 1—N restores.
Backups keep their descriptive columns so history survives deletion of a connection.
