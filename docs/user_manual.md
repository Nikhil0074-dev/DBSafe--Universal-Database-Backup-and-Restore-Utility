# User manual

## Roles
* **Administrator** — everything: connections, backups, restores, schedules, deletion, users, logs.
* **Operator** — view databases, create backups, view history, verify and restore backups.

## Add a database
Databases → *Add database*. Choose the type, fill in the details, press **Test connection**, then **Save**.
For SQLite enter the full file path. Passwords are stored encrypted.

## Create a backup
Backups → *Create backup*. *Selective* lets you tick tables. Options: compression (GZIP/ZIP/none),
encryption (AES-256, uses `DBSAFE_ENCRYPTION_KEY`), verification (checksum + deep readability test).
Files are named `<database>_<YYYY-MM-DD_HH-MM-SS>.<ext>[.gz|.zip][.enc]` and get an ID like `BK-20260920-00001`.
Administrators may give a destination folder inside the allowed backup locations.

## Verify
*Verify* recomputes the SHA-256 and compares it with the stored value. *Deep verify* additionally decrypts and
decompresses into a temporary area. A failed check reports *Integrity Verification Failed*.

## Restore
Restore → choose the backup and a compatible target connection. The target database name defaults to the
connection's database; enter another name to restore side-by-side. Keep *safety backup* ticked to snapshot the
current target first. The result lists each step (verify, safety backup, decrypt, decompress, restore, verify).
If the checksum does not match, nothing is touched.

## Schedules
Administrators create schedules (hourly, every 6 hours, daily, weekly, monthly or cron). Retention removes
only *scheduled* backups: keep N days, and/or the newest backup of the last N days/weeks/months. The newest
backup is never removed. **Run now** starts a schedule immediately.

## Storage, logs, notifications
Storage shows usage and per-database consumption (warning at `DBSAFE_STORAGE_WARN_PERCENT`). Logs (admin) list
every operation. Set `DBSAFE_SMTP_*` and `DBSAFE_NOTIFY_TO` to receive e-mails for failures, restores and low storage.

## Troubleshooting
* *"mysqldump was not found"* — install the client tools or set `MYSQLDUMP_PATH`.
* *"Decryption failed"* — the encryption key differs from the one used for the backup.
* *"Stored database password cannot be decrypted"* — `DBSAFE_SECRET_KEY` changed; re-enter the password.
* Application logs: `logs/application.log`, `backup.log`, `restore.log`, `error.log`.
