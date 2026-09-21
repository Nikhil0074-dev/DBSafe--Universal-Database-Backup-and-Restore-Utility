"""Common interface implemented by every database adapter."""
from abc import ABC, abstractmethod

from ..exceptions import DBSafeError
from ..utils.command_runner import find_executable


class DatabaseAdapter(ABC):
    """Adapter contract.

    An adapter instance is bound to ONE database (``self.database``). To work on a
    different database (e.g. a restore target) create a new adapter for it.
    """

    db_type = ""
    backup_extension = ".bak"

    def __init__(self, params, config=None):
        self.host = params.get("host")
        self.port = params.get("port")
        self.username = params.get("username")
        self.password = params.get("password") or ""
        self.database = params.get("database_name")
        self.extra = params.get("extra") or {}
        self.config = config or {}
        self._conn = None

    # -- connection ---------------------------------------------------------
    @abstractmethod
    def connect(self):
        """Open and return a connection (also stored in ``self._conn``)."""

    def disconnect(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # pragma: no cover
                pass
            self._conn = None

    @abstractmethod
    def _probe(self):
        """Connect and return a dict with server/database/version information.
        Raises on failure."""

    def test_connection(self):
        """Return ``{"ok": bool, "message": str, ...}``; never raises."""
        try:
            info = self._probe()
            return {"ok": True, "message": "Connection successful", **info}
        except DBSafeError as exc:
            return {"ok": False, "message": exc.message}
        except Exception as exc:
            return {"ok": False, "message": self._clean_error(exc)}
        finally:
            self.disconnect()

    def _clean_error(self, exc):
        text = str(exc).strip() or exc.__class__.__name__
        if self.password:
            text = text.replace(self.password, "********")
        return text

    # -- metadata -----------------------------------------------------------
    @abstractmethod
    def get_databases(self):
        """Names of the databases available on the server."""

    @abstractmethod
    def get_tables(self):
        """Tables (or collections) of ``self.database``."""

    @abstractmethod
    def get_database_information(self):
        """Dictionary of descriptive information about ``self.database``."""

    @abstractmethod
    def database_exists(self):
        """True if ``self.database`` exists on the server."""

    # -- backup / restore ---------------------------------------------------
    @abstractmethod
    def create_backup(self, dest_path, tables=None):
        """Write a raw (uncompressed, unencrypted) backup to *dest_path*.
        *tables* restricts the backup to those tables (selective backup)."""

    @abstractmethod
    def restore_backup(self, source_path, source_database=None):
        """Restore the raw backup at *source_path* into ``self.database``.
        *source_database* is the name of the database the backup was taken from."""

    @abstractmethod
    def verify_restore(self, expected_tables=None):
        """Check the restored database. Returns ``{"ok": bool, "message": str, ...}``."""

    # -- helpers ------------------------------------------------------------
    def tool(self, name):
        """Path of an external client tool such as ``mysqldump``."""
        return find_executable(name, self.config.get(name.upper().replace("-", "_") + "_PATH"))

    @property
    def command_timeout(self):
        return self.config.get("COMMAND_TIMEOUT_SECONDS") or None

    @staticmethod
    def _compare_tables(present, expected):
        if not expected:
            return []
        return sorted(set(expected) - set(present))

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc_info):
        self.disconnect()
        return False
