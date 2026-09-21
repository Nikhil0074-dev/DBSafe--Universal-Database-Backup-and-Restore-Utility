# Installation

1. Install Python 3.9+ and (for the databases you use) the client tools:
   * MySQL/MariaDB: `mysqldump`, `mysql`
   * PostgreSQL: `pg_dump`, `psql`
   * MongoDB: `mongodump`, `mongorestore`
2. Create a virtual environment and install dependencies: `pip install -r requirements.txt`.
   The driver packages are imported lazily; a missing driver only affects that database type.
3. Copy `.env.example` to `.env` and adjust (all optional).
4. `python run.py` → http://127.0.0.1:5000. Default login `admin` / `Admin@123`.
5. Optional: `python scripts/initialize_db.py` creates the database without starting the server.

## Production
* Put the app behind an HTTPS reverse proxy and set `DBSAFE_SESSION_COOKIE_SECURE=true`.
* Serve with a WSGI server using a single process, e.g. `waitress-serve --port 5000 run:app`
  (the in-process scheduler must not be duplicated).
* Back up `database/dbsafe.db`, `instance/` and your encryption key.
* Allow extra backup locations (network drive, second disk) with `DBSAFE_ALLOWED_BACKUP_ROOTS`.

## Maintenance scripts
* `python scripts/cleanup_backups.py` — apply retention policies now.
* `python scripts/test_connections.py` — test all saved connections.
