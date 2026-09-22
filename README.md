# DBSafe - Universal Database Backup and Restore Utility

A modular web application (Flask + SQLite metadata store) that backs up, verifies, schedules and
restores **MySQL/MariaDB, PostgreSQL, SQLite and MongoDB** databases from one interface.

**Features:** role-based login (admin / operator) · connection management with encrypted passwords ·
full and selective backups · GZIP/ZIP compression · AES-256-GCM encryption · SHA-256 integrity
checks (plus deep verification) · restore with automatic safety backup and post-restore verification ·
APScheduler schedules with retention (days and daily/weekly/monthly) · backup history with
search/sort/filter · storage monitor · audit log · optional e-mail notifications · adapter architecture
for adding more databases.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional; every setting has a default
python run.py
```

Open <http://127.0.0.1:5000> and sign in with **admin / Admin@123** (override with
`DBSAFE_ADMIN_USERNAME` / `DBSAFE_ADMIN_PASSWORD` before the first start). **Change the password
under Account.**

On first start DBSafe creates `database/dbsafe.db`, `instance/secret.key` and `instance/encryption.key`.
Set `DBSAFE_ENCRYPTION_KEY` in `.env` if you want to control the backup-encryption passphrase.
**Keep a copy of the key: encrypted backups cannot be restored without it.**

### Requirements
* Python 3.9+ (developed and tested on 3.12)
* SQLite backups need nothing else (built-in backup API).
* MySQL needs `mysqldump` and `mysql` on the PATH; PostgreSQL needs `pg_dump` and `psql`;
  MongoDB needs `mongodump` and `mongorestore` (MongoDB Database Tools). Or set the
  `*_PATH` variables in `.env`.

## Using it
1. **Databases → Add database**, press *Test connection*, save.
2. **Backups → Create backup** (full or selective, compression, encryption, verification).
3. **Restore**: pick a backup, a compatible target connection and target database name; a safety backup of
   the current target is taken first (unless you turn it off).
4. **Schedules** (admin): hourly … monthly or a cron expression, with retention rules.
5. **Storage / Logs / Users** for monitoring and administration.

## Tests
```bash
pytest
```
83 tests cover encryption, compression, checksums, authentication, CSRF, roles, backup/restore round trips
(SQLite end-to-end), retention, scheduling, path-traversal protection, page rendering, and the MySQL /
PostgreSQL / MongoDB adapters (command construction with a fake runner; no servers needed).

## Project layout
See `docs/architecture.md`. Documentation: `docs/installation.md`, `docs/user_manual.md`,
`docs/api_documentation.md`, `docs/database_design.md`.

