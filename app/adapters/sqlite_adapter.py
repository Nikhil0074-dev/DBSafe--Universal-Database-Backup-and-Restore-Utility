"""SQLite adapter using the built-in sqlite3 backup API (no external tools)."""
import sqlite3
from pathlib import Path

from ..exceptions import AdapterError
from .base_adapter import DatabaseAdapter

SQLITE_MAGIC = b"SQLite format 3\x00"


def _quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


class SQLiteAdapter(DatabaseAdapter):
    db_type = "sqlite"
    backup_extension = ".db"

    @property
    def path(self):
        return Path(str(self.database)).expanduser()

    def _open(self):
        path = self.path
        if not path.is_file():
            raise AdapterError(f"SQLite database file not found: {path}")
        try:
            return sqlite3.connect(str(path), timeout=30)
        except sqlite3.Error as exc:
            raise AdapterError(f"Cannot open SQLite database: {exc}") from exc

    def connect(self):
        self.disconnect()
        self._conn = self._open()
        return self._conn

    def _probe(self):
        conn = self._open()
        try:
            version = conn.execute("SELECT sqlite_version()").fetchone()[0]
            tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            raise AdapterError(f"Not a valid SQLite database: {exc}") from exc
        finally:
            conn.close()
        return {"server": f"SQLite {version}", "version": version,
                "database": str(self.path), "tables": tables}

    def get_databases(self):
        return [str(self.path)] if self.path.is_file() else []

    def get_tables(self):
        conn = self._open()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name").fetchall()
            return [row[0] for row in rows]
        except sqlite3.DatabaseError as exc:
            raise AdapterError(f"Cannot read tables: {exc}") from exc
        finally:
            conn.close()

    def get_database_information(self):
        conn = self._open()
        try:
            return {
                "type": "sqlite",
                "path": str(self.path),
                "size_bytes": self.path.stat().st_size,
                "tables": len(self.get_tables()),
                "sqlite_version": conn.execute("SELECT sqlite_version()").fetchone()[0],
                "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
                "page_size": conn.execute("PRAGMA page_size").fetchone()[0],
            }
        except sqlite3.DatabaseError as exc:
            raise AdapterError(f"Cannot read database information: {exc}") from exc
        finally:
            conn.close()

    def database_exists(self):
        return self.path.is_file()

    # -- backup -------------------------------------------------------------
    def create_backup(self, dest_path, tables=None):
        dest = Path(dest_path)
        if not tables:
            self._full_backup(dest)
        else:
            self._selective_backup(dest, list(tables))

    def _full_backup(self, dest):
        source = self._open()
        target = sqlite3.connect(str(dest))
        try:
            source.backup(target)
        except sqlite3.Error as exc:
            raise AdapterError(f"SQLite backup failed: {exc}") from exc
        finally:
            target.close()
            source.close()

    def _selective_backup(self, dest, tables):
        available = set(self.get_tables())
        missing = [t for t in tables if t not in available]
        if missing:
            raise AdapterError(f"Table(s) not found: {', '.join(missing)}")
        target = sqlite3.connect(str(dest))
        try:
            target.execute("ATTACH DATABASE ? AS src", (str(self.path.resolve()),))
            for table in tables:
                row = target.execute(
                    "SELECT sql FROM src.sqlite_master WHERE type = 'table' AND name = ?", (table,)
                ).fetchone()
                if not row or not row[0]:
                    raise AdapterError(f"Cannot read the definition of table '{table}'")
                target.execute(row[0])
                target.execute(f"INSERT INTO main.{_quote(table)} SELECT * FROM src.{_quote(table)}")
            marks = ",".join("?" for _ in tables)
            extras = target.execute(
                "SELECT sql FROM src.sqlite_master WHERE type IN ('index', 'trigger') "
                f"AND sql IS NOT NULL AND tbl_name IN ({marks})", tables).fetchall()
            for (statement,) in extras:
                target.execute(statement)
            target.commit()
            target.execute("DETACH DATABASE src")
        except sqlite3.Error as exc:
            raise AdapterError(f"SQLite selective backup failed: {exc}") from exc
        finally:
            target.close()

    # -- restore ------------------------------------------------------------
    @staticmethod
    def _validate_backup_file(path):
        path = Path(path)
        if not path.is_file():
            raise AdapterError("Backup file not found")
        with open(path, "rb") as handle:
            if handle.read(16) != SQLITE_MAGIC:
                raise AdapterError("The backup is not a valid SQLite database file")
        conn = sqlite3.connect(str(path))
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            raise AdapterError(f"The backup file is corrupt: {exc}") from exc
        finally:
            conn.close()
        if result != "ok":
            raise AdapterError(f"The backup failed the SQLite integrity check: {result}")

    def restore_backup(self, source_path, source_database=None):
        self._validate_backup_file(source_path)
        target = self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(str(source_path))
        destination = sqlite3.connect(str(target))
        try:
            source.backup(destination)
        except sqlite3.Error as exc:
            raise AdapterError(f"SQLite restore failed: {exc}") from exc
        finally:
            destination.close()
            source.close()

    def verify_restore(self, expected_tables=None):
        if not self.path.is_file():
            return {"ok": False, "message": "Restored database file was not found"}
        conn = self._open()
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            tables = self.get_tables()
            rows = 0
            for table in tables:
                rows += conn.execute(f"SELECT COUNT(*) FROM {_quote(table)}").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            return {"ok": False, "message": f"Verification failed: {exc}"}
        finally:
            conn.close()
        missing = self._compare_tables(tables, expected_tables)
        ok = integrity == "ok" and not missing
        if integrity != "ok":
            message = f"Integrity check failed: {integrity}"
        elif missing:
            message = f"Missing tables after restore: {', '.join(missing)}"
        else:
            message = "Restore verified"
        return {"ok": ok, "message": message, "integrity": integrity,
                "tables": len(tables), "rows": rows, "missing_tables": missing}
