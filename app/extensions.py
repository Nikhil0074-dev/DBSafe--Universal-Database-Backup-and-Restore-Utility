"""Shared infrastructure: a small worker pool for long-running backup/restore jobs."""
import logging
from concurrent.futures import ThreadPoolExecutor

_executor = None


def run_in_background(app, func, *args, **kwargs):
    """Run ``func`` in a worker thread inside an application context."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=app.config.get("WORKER_THREADS", 4),
                                       thread_name_prefix="dbsafe-worker")

    def runner():
        with app.app_context():
            try:
                return func(*args, **kwargs)
            except Exception:  # the service functions record failures themselves
                logging.getLogger("dbsafe").exception("Background task crashed")

    return _executor.submit(runner)
