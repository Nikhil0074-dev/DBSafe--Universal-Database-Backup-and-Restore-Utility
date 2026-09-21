"""MongoDB adapter (pymongo + mongodump / mongorestore, single-file archives)."""
import os
import tempfile
from contextlib import contextmanager
from urllib.parse import quote_plus

from ..exceptions import AdapterError, ValidationError
from ..utils.command_runner import run_command
from ..utils.validation import is_safe_identifier
from .base_adapter import DatabaseAdapter

_SYSTEM_DATABASES = {"admin", "local", "config"}


def _driver():
    try:
        import pymongo
    except ImportError as exc:
        raise AdapterError("The 'pymongo' package is not installed. Run: pip install pymongo") from exc
    return pymongo


class MongoDBAdapter(DatabaseAdapter):
    db_type = "mongodb"
    backup_extension = ".archive"

    def _uri(self):
        credentials = ""
        query = ""
        if self.username:
            credentials = f"{quote_plus(self.username)}:{quote_plus(self.password)}@"
            query = f"?authSource={quote_plus(self.extra.get('auth_source') or 'admin')}"
        return f"mongodb://{credentials}{self.host or 'localhost'}:{int(self.port or 27017)}/{query}"

    def _client(self):
        pymongo = _driver()
        return pymongo.MongoClient(self._uri(), serverSelectionTimeoutMS=8000)

    def _run(self, func):
        client = self._client()
        try:
            return func(client)
        except _driver().errors.PyMongoError as exc:
            raise AdapterError(self._clean_error(exc)) from exc
        finally:
            client.close()

    def connect(self):
        self.disconnect()
        client = self._client()
        try:
            client.admin.command("ping")
        except _driver().errors.PyMongoError as exc:
            client.close()
            raise AdapterError(self._clean_error(exc)) from exc
        self._conn = client
        return client

    def _probe(self):
        def probe(client):
            client.admin.command("ping")
            return client.server_info().get("version", "")
        version = self._run(probe)
        return {"server": f"{self.host}:{self.port}", "version": str(version), "database": self.database}

    def get_databases(self):
        names = self._run(lambda c: c.list_database_names())
        return [n for n in names if n not in _SYSTEM_DATABASES]

    def get_tables(self):
        names = self._run(lambda c: c[self.database].list_collection_names())
        return sorted(n for n in names if not n.startswith("system."))

    def database_exists(self):
        return self.database in self._run(lambda c: c.list_database_names())

    def get_database_information(self):
        def info(client):
            stats = client[self.database].command("dbStats")
            return {"type": "mongodb", "server": f"{self.host}:{self.port}",
                    "version": client.server_info().get("version", ""),
                    "database": self.database, "tables": int(stats.get("collections", 0)),
                    "size_bytes": int(stats.get("dataSize", 0))}
        return self._run(info)

    @contextmanager
    def _config_file(self):
        """YAML config so the credentials never appear on a command line."""
        fd, name = tempfile.mkstemp(prefix="dbsafe_", suffix=".yml", dir=self.config.get("TEMP_DIR"))
        try:
            uri = self._uri().replace("\\", "\\\\").replace('"', '\\"')
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f'uri: "{uri}"\n')
            yield name
        finally:
            try:
                os.remove(name)
            except OSError:
                pass

    def create_backup(self, dest_path, tables=None):
        if not is_safe_identifier(self.database):
            raise ValidationError(f"Unsafe database name: {self.database!r}")
        exe = self.tool("mongodump")
        with self._config_file() as cfg:
            args = [exe, f"--config={cfg}", f"--archive={dest_path}"]
            if tables:
                for name in tables:
                    if not is_safe_identifier(name.replace(".", "_")):
                        raise ValidationError(f"Unsafe collection name: {name!r}")
                    args.append(f"--nsInclude={self.database}.{name}")
            else:
                args.append(f"--nsInclude={self.database}.*")
            run_command(args, timeout=self.command_timeout, secrets=[self.password])

    def restore_backup(self, source_path, source_database=None):
        if not is_safe_identifier(self.database):
            raise ValidationError(f"Unsafe database name: {self.database!r}")
        exe = self.tool("mongorestore")
        with self._config_file() as cfg:
            args = [exe, f"--config={cfg}", f"--archive={source_path}", "--drop"]
            source = source_database or self.database
            if source != self.database:
                args += [f"--nsFrom={source}.*", f"--nsTo={self.database}.*"]
            run_command(args, timeout=self.command_timeout, secrets=[self.password])

    def verify_restore(self, expected_tables=None):
        try:
            collections = self.get_tables()
        except AdapterError as exc:
            return {"ok": False, "message": f"Verification failed: {exc.message}"}
        missing = self._compare_tables(collections, expected_tables)
        return {"ok": not missing, "tables": len(collections), "missing_tables": missing,
                "message": "Restore verified" if not missing
                else f"Missing collections after restore: {', '.join(missing)}"}
