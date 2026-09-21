"""Create the metadata database and the first administrator.

Usage:  python scripts/initialize_db.py
"""
import _bootstrap  # noqa: F401

from app import create_app


def main():
    app = create_app({"SCHEDULER_ENABLED": False})
    print(f"Database ready at {app.config['DATABASE_PATH']}")
    print(f"Administrator: {app.config['ADMIN_USERNAME']} (created only when no users existed)")
    print("Log in and change the default password.")


if __name__ == "__main__":
    main()
