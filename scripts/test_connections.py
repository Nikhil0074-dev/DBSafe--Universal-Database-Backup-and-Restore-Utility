"""Test every saved database connection and print the result.

Usage:  python scripts/test_connections.py
"""
import sys

import _bootstrap  # noqa: F401

from app import create_app
from app.repositories import database_repository
from app.services import connection_service


def main():
    app = create_app({"SCHEDULER_ENABLED": False, "LOG_TO_CONSOLE": False})
    failures = 0
    with app.app_context():
        connections = database_repository.list_connections()
        if not connections:
            print("No connections configured.")
        for connection in connections:
            result = connection_service.test_connection(connection)
            mark = "OK  " if result["ok"] else "FAIL"
            failures += 0 if result["ok"] else 1
            print(f"[{mark}] {connection.name} ({connection.database_type}): {result['message']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
