"""DBSafe application factory."""
import logging
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from config.config import build_config
from config.logging_config import setup_logging

from .exceptions import DBSafeError

__version__ = "1.0.0"
log = logging.getLogger("dbsafe")

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(test_config=None):
    cfg = build_config(test_config)
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(cfg)

    for key in ("BACKUP_DIR", "TEMP_DIR", "LOG_DIR", "INSTANCE_DIR"):
        Path(app.config[key]).mkdir(parents=True, exist_ok=True)
    Path(app.config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    setup_logging(app.config["LOG_DIR"], app.config["LOG_LEVEL"], app.config["LOG_TO_CONSOLE"])

    with app.app_context():
        from .repositories import base
        base.init_database()

    _register_hooks(app)
    _register_error_handlers(app)

    from .api import register_blueprints
    register_blueprints(app)

    if app.config["SCHEDULER_ENABLED"]:
        from .services import scheduler_service
        scheduler_service.init_scheduler(app)
    return app


def _register_hooks(app):
    from .api.security import check_csrf, csrf_token, current_user

    @app.context_processor
    def inject_globals():
        return {"user": current_user(), "csrf_token": csrf_token, "app_version": __version__}

    @app.before_request
    def csrf_protect():
        if request.method in _UNSAFE_METHODS and request.path.startswith("/api/"):
            check_csrf()

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


def _register_error_handlers(app):
    @app.errorhandler(DBSafeError)
    def handle_dbsafe_error(error):
        body = {"error": error.message}
        if error.details:
            body["details"] = error.details
        if request.path.startswith("/api/"):
            return jsonify(body), error.status_code
        return f"{error.message}", error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description or error.name), error.code
        return error

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        log.exception("Unhandled error: %s", error)
        if request.path.startswith("/api/"):
            return jsonify(error="Internal server error"), 500
        return "Internal server error", 500
