"""Apply every schedule's retention policy (handy for a cron job).

Usage:  python scripts/cleanup_backups.py
"""
import _bootstrap  # noqa: F401

from app import create_app
from app.services import storage_service


def main():
    app = create_app({"SCHEDULER_ENABLED": False, "LOG_TO_CONSOLE": False})
    with app.app_context():
        removed = storage_service.apply_retention_all()
    print(f"Removed {removed} expired backup(s)")


if __name__ == "__main__":
    main()
