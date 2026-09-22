"""Logging setup: application, backup, restore and error log files."""
import logging
import logging.handlers
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def _file_handler(path, level):
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    return handler


def _reset(logger):
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # pragma: no cover
            pass


def setup_logging(log_dir, level="INFO", console=True):
    """Configure the ``dbsafe`` logger family. Safe to call more than once."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    lvl = getattr(logging, str(level).upper(), logging.INFO)

    root = logging.getLogger("dbsafe")
    _reset(root)
    root.setLevel(lvl)
    root.propagate = False
    root.addHandler(_file_handler(log_dir / "application.log", lvl))
    root.addHandler(_file_handler(log_dir / "error.log", logging.ERROR))
    if console:
        stream = logging.StreamHandler()
        stream.setLevel(lvl)
        stream.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(stream)

    for name, filename in (("dbsafe.backup", "backup.log"), ("dbsafe.restore", "restore.log")):
        child = logging.getLogger(name)
        _reset(child)
        child.setLevel(lvl)
        child.propagate = True  # also reaches application.log / error.log
        child.addHandler(_file_handler(log_dir / filename, lvl))
    return root
