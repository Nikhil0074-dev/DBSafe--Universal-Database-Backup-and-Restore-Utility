"""Session authentication, role checks and CSRF protection."""
import hmac
import secrets
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from ..exceptions import AuthenticationError, PermissionDenied, ValidationError
from ..repositories import user_repository


def current_user():
    """The logged-in user as a dict, or None. Re-read from the DB on every request
    so deleted users and role changes take effect immediately."""
    if "dbsafe_user" in g:
        return g.dbsafe_user
    user = None
    user_id = session.get("user_id")
    if user_id:
        row = user_repository.get(user_id)
        if row:
            user = {"id": row.id, "username": row.username, "role": row.role}
    g.dbsafe_user = user
    return user


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user():
            raise AuthenticationError("Authentication required")
        return func(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                raise AuthenticationError("Authentication required")
            if user["role"] not in roles:
                raise PermissionDenied("You do not have permission to perform this action")
            return func(*args, **kwargs)
        return wrapper
    return decorator


admin_required = roles_required("admin")


def page_login_required(*roles):
    """Decorator for HTML pages: redirect to the login page, or 403 for the wrong role."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("pages.login"))
            if roles and user["role"] not in roles:
                abort(403)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(24)
    return session["csrf"]


def check_csrf():
    """Reject state-changing API calls that lack the session's CSRF token."""
    sent = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf", "")
    if not expected or not hmac.compare_digest(sent, expected):
        raise PermissionDenied("Invalid or missing CSRF token")


def json_body():
    data = request.get_json(silent=True)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValidationError("The request body must be a JSON object")
    return data
