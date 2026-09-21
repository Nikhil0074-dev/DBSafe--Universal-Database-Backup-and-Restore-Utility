"""MySQL / MariaDB adapter (mysql-connector-python + mysqldump / mysql client)."""
import os
import shlex
import tempfile
from contextlib import contextmanager
from pathlib import Path

from ..exceptions import AdapterError, ValidationError
from ..utils.command_runner import run_command
from ..utils.validation import is_safe_identifier
from .base_adapter import DatabaseAdapter

_SYSTEM_DATABASES = {"information_schema", "performance_schema", "sys", "mysql"}


def _driver():
    try:
        import mysql.connector as connector
    except ImportError as exc:
        raise AdapterError(
            "The 'mysql-connector-python' package is not installed. "
            "Run: pip install mysql-connector-python") from exc
    return connector


def _option_value(value):
    """Quote a value for a MySQL option file."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


class MySQLAdapter(DatabaseAdapter):
    db_type = "mysql"
    backup_extension = ".sql"

    def _open(self, database):
        connector = _driver()
        kwargs = dict(host=self.host or "localhost", port=int(self.port or 3306),
                      user=self.username, password=self.password, connection_timeout=10)
        if database:
            kwargs["database"] = database
        try:
            return connector.connect(**kwargs)
        except connector.Error as exc:
            raise AdapterError(self._clean_error(exc)) from exc

    def connect(self):
        self.disconnect()
        self._conn = self._open(self.database)
        return self._conn

    def _query(self, sql, database="__default__"):
        conn = self._open(self.database if database == "__default__" else database)
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except _driver().Error as exc:
            raise AdapterError(self._clean_error(exc)) from exc
        finally:
            conn.close()

    def _probe(self):
        rows = self._query("SELECT VERSION(), DATABASE()")
        version, database = rows[0]
        return {"server": f"{self.host}:{self.port}", "version": str(version), "database": database}

    def get_databases(self):
        rows = self._query("SHOW DATABASES", database=None)
        return [r[0] for r in rows if r[0].lower() not in _SYSTEM_DATABASES]

    def get_tables(self):
        rows = self._query("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        return [r[0] for r in rows]

    def database_exists(self):
        return self.database in [r[0] for r in self._query("SHOW DATABASES", database=None)]

    def get_database_information(self):
        rows = self._query(
            "SELECT COUNT(*), COALESCE(SUM(data_length + index_length), 0) "
            "FROM information_schema.tables WHERE table_schema = DATABASE()")
        version = self._query("SELECT VERSION()")[0][0]
        return {"type": "mysql", "server": f"{self.host}:{self.port}", "version": str(version),
                "database": self.database, "tables": int(rows[0][0]), "size_bytes": int(rows[0][1])}

    # -- external tools -----------------------------------------------------
    @contextmanager
    def _defaults_file(self):
        """Temporary option file so the password never appears on a command line."""
        fd, name = tempfile.mkstemp(prefix="dbsafe_", suffix=".cnf", dir=self.config.get("TEMP_DIR"))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("[client]\n")
                handle.write(f"user={_option_value(self.username or '')}\n")
                handle.write(f"password={_option_value(self.password)}\n")
                handle.write(f"host={_option_value(self.host or 'localhost')}\n")
                handle.write(f"port={int(self.port or 3306)}\n")
            yield name
        finally:
            try:
                os.remove(name)
            except OSError:
                pass

    def _require_identifier(self, name):
        if not is_safe_identifier(name):
            raise ValidationError(f"Unsafe database name: {name!r}")

    def create_backup(self, dest_path, tables=None):
        self._require_identifier(self.database)
        for table in tables or []:
            if not is_safe_identifier(table):
                raise ValidationError(f"Unsafe table name: {table!r}")
        exe = self.tool("mysqldump")
        with self._defaults_file() as cnf:
            args = [exe, f"--defaults-extra-file={cnf}", "--single-transaction", "--routines",
                    "--triggers", "--events", "--default-character-set=utf8mb4",
                    f"--result-file={dest_path}"]
            args += shlex.split(self.config.get("MYSQLDUMP_EXTRA_ARGS") or "")
            args.append(self.database)
            args += list(tables or [])
            run_command(args, timeout=self.command_timeout, secrets=[self.password])
        dest = Path(dest_path)
        if not dest.is_file() or dest.stat().st_size == 0:
            raise AdapterError("mysqldump did not produce any output")

    def restore_backup(self, source_path, source_database=None):
        self._require_identifier(self.database)
        conn = self._open(None)
        try:
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self.database}` CHARACTER SET utf8mb4")
            cursor.close()
        except _driver().Error as exc:
            raise AdapterError(self._clean_error(exc)) from exc
        finally:
            conn.close()
        exe = self.tool("mysql")
        with self._defaults_file() as cnf:
            run_command([exe, f"--defaults-extra-file={cnf}", "--default-character-set=utf8mb4",
                         self.database],
                        stdin_path=source_path, timeout=self.command_timeout, secrets=[self.password])

    def verify_restore(self, expected_tables=None):
        try:
            tables = self.get_tables()
        except AdapterError as exc:
            return {"ok": False, "message": f"Verification failed: {exc.message}"}
        missing = self._compare_tables(tables, expected_tables)
        return {"ok": not missing, "tables": len(tables), "missing_tables": missing,
                "message": "Restore verified" if not missing
                else f"Missing tables after restore: {', '.join(missing)}"}
