"""PostgreSQL adapter (psycopg 3 + pg_dump / psql)."""
import re

from ..exceptions import AdapterError, ValidationError
from ..utils.command_runner import run_command
from ..utils.validation import is_safe_identifier
from .base_adapter import DatabaseAdapter

_TABLE_PATTERN = re.compile(r"^[A-Za-z0-9_$.\-]{1,128}$")


def _driver():
    try:
        import psycopg
    except ImportError as exc:
        raise AdapterError(
            "The 'psycopg' package is not installed. Run: pip install \"psycopg[binary]\"") from exc
    return psycopg


class PostgresAdapter(DatabaseAdapter):
    db_type = "postgresql"
    backup_extension = ".sql"

    def _open(self, dbname):
        psycopg = _driver()
        try:
            conn = psycopg.connect(host=self.host or "localhost", port=int(self.port or 5432),
                                   user=self.username, password=self.password, dbname=dbname,
                                   connect_timeout=10, autocommit=True)
        except psycopg.Error as exc:
            raise AdapterError(self._clean_error(exc)) from exc
        return conn

    def _maintenance_open(self):
        """Connect to a maintenance database (used when the target may not exist)."""
        last = None
        for name in ("postgres", "template1", self.database):
            try:
                return self._open(name)
            except AdapterError as exc:
                last = exc
        raise last

    def _query(self, sql, params=None, maintenance=False):
        conn = self._maintenance_open() if maintenance else self._open(self.database)
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        except _driver().Error as exc:
            raise AdapterError(self._clean_error(exc)) from exc
        finally:
            conn.close()

    def connect(self):
        self.disconnect()
        self._conn = self._open(self.database)
        return self._conn

    def _probe(self):
        version, database = self._query("SELECT version(), current_database()")[0]
        return {"server": f"{self.host}:{self.port}", "version": str(version).split(",")[0],
                "database": database}

    def get_databases(self):
        rows = self._query(
            "SELECT datname FROM pg_database WHERE NOT datistemplate AND datallowconn ORDER BY 1",
            maintenance=True)
        return [r[0] for r in rows]

    def get_tables(self):
        rows = self._query(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema') "
            "ORDER BY 1, 2")
        return [name if schema == "public" else f"{schema}.{name}" for schema, name in rows]

    def database_exists(self):
        rows = self._query("SELECT 1 FROM pg_database WHERE datname = %s", (self.database,),
                           maintenance=True)
        return bool(rows)

    def get_database_information(self):
        version = self._query("SELECT version()")[0][0]
        size = self._query("SELECT pg_database_size(current_database())")[0][0]
        return {"type": "postgresql", "server": f"{self.host}:{self.port}",
                "version": str(version).split(",")[0], "database": self.database,
                "tables": len(self.get_tables()), "size_bytes": int(size)}

    def _env(self):
        return {"PGPASSWORD": self.password, "PGCONNECT_TIMEOUT": "15"}

    def _conn_args(self):
        return ["--host", str(self.host or "localhost"), "--port", str(int(self.port or 5432)),
                "--username", str(self.username), "--no-password"]

    def create_backup(self, dest_path, tables=None):
        if not is_safe_identifier(self.database):
            raise ValidationError(f"Unsafe database name: {self.database!r}")
        exe = self.tool("pg_dump")
        args = [exe] + self._conn_args() + ["--format=plain", "--clean", "--if-exists",
                                            "--no-owner", "--no-privileges", "--file", str(dest_path)]
        for table in tables or []:
            if not _TABLE_PATTERN.match(table):
                raise ValidationError(f"Unsafe table name: {table!r}")
            args += ["--table", table]
        args.append(self.database)
        run_command(args, env=self._env(), timeout=self.command_timeout, secrets=[self.password])

    def restore_backup(self, source_path, source_database=None):
        if not is_safe_identifier(self.database):
            raise ValidationError(f"Unsafe database name: {self.database!r}")
        psycopg = _driver()
        if not self.database_exists():
            conn = self._maintenance_open()
            try:
                conn.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(
                    psycopg.sql.Identifier(self.database)))
            except psycopg.Error as exc:
                raise AdapterError(self._clean_error(exc)) from exc
            finally:
                conn.close()
        exe = self.tool("psql")
        args = [exe] + self._conn_args() + ["--set", "ON_ERROR_STOP=1", "--single-transaction",
                                            "--quiet", "--dbname", self.database,
                                            "--file", str(source_path)]
        run_command(args, env=self._env(), timeout=self.command_timeout, secrets=[self.password])

    def verify_restore(self, expected_tables=None):
        try:
            tables = self.get_tables()
        except AdapterError as exc:
            return {"ok": False, "message": f"Verification failed: {exc.message}"}
        missing = self._compare_tables(tables, expected_tables)
        return {"ok": not missing, "tables": len(tables), "missing_tables": missing,
                "message": "Restore verified" if not missing
                else f"Missing tables after restore: {', '.join(missing)}"}
