"""Adapter registry. Add a new database by writing an adapter and registering it here."""
from ..exceptions import ValidationError
from .base_adapter import DatabaseAdapter
from .mongodb_adapter import MongoDBAdapter
from .mysql_adapter import MySQLAdapter
from .postgres_adapter import PostgresAdapter
from .sqlite_adapter import SQLiteAdapter

ADAPTERS = {
    "mysql": MySQLAdapter,
    "postgresql": PostgresAdapter,
    "sqlite": SQLiteAdapter,
    "mongodb": MongoDBAdapter,
}


def get_adapter(db_type, params, config=None):
    try:
        adapter_class = ADAPTERS[db_type]
    except KeyError:
        raise ValidationError(f"Unsupported database type: {db_type}") from None
    return adapter_class(params, config)


__all__ = ["ADAPTERS", "DatabaseAdapter", "get_adapter"]
