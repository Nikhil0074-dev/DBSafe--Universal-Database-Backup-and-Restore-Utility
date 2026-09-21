"""Authentication and user management."""
import threading
import time

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from ..exceptions import (AuthenticationError, ConflictError, NotFoundError, TooManyAttempts,
                          ValidationError)
from ..repositories import user_repository
from ..utils.validation import validate_password, validate_role, validate_username

_failures = {}
_lock = threading.Lock()
_DUMMY_HASH = generate_password_hash("dbsafe-dummy-password", method="pbkdf2:sha256")


def hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256")


def _key(username, ip):
    return f"{(username or '').lower()}|{ip or ''}"


def _recent_failures(key):
    window = current_app.config["LOGIN_WINDOW_SECONDS"]
    cutoff = time.time() - window
    attempts = [t for t in _failures.get(key, []) if t > cutoff]
    _failures[key] = attempts
    return attempts


def reset_login_attempts():
    with _lock:
        _failures.clear()


def authenticate(username, password, ip=None):
    """Return the User or raise. Repeated failures for a user/IP are temporarily blocked."""
    key = _key(username, ip)
    with _lock:
        if len(_recent_failures(key)) >= current_app.config["LOGIN_MAX_ATTEMPTS"]:
            raise TooManyAttempts("Too many failed login attempts. Please wait a few minutes.")
    user = user_repository.get_by_username(username) if username else None
    # Always run a hash check so the response time does not reveal valid usernames.
    valid = check_password_hash(user.password_hash if user else _DUMMY_HASH, password or "")
    if not user or not valid:
        with _lock:
            _failures.setdefault(key, []).append(time.time())
        raise AuthenticationError("Invalid username or password")
    with _lock:
        _failures.pop(key, None)
    return user


def create_user(username, password, role):
    username = validate_username(username)
    validate_password(password)
    validate_role(role)
    if user_repository.get_by_username(username):
        raise ConflictError("This username already exists")
    return user_repository.get(user_repository.create(username, hash_password(password), role))


def update_user(user_id, role=None, password=None, acting_user_id=None):
    user = user_repository.get(user_id)
    if not user:
        raise NotFoundError("User not found")
    fields = {}
    if role is not None:
        validate_role(role)
        if user.role == "admin" and role != "admin" and user_repository.count_admins() <= 1:
            raise ValidationError("At least one administrator is required")
        fields["role"] = role
    if password:
        validate_password(password)
        fields["password_hash"] = hash_password(password)
    if fields:
        user_repository.update(user_id, **fields)
    return user_repository.get(user_id)


def delete_user(user_id, acting_user_id):
    user = user_repository.get(user_id)
    if not user:
        raise NotFoundError("User not found")
    if user.id == acting_user_id:
        raise ValidationError("You cannot delete your own account")
    if user.role == "admin" and user_repository.count_admins() <= 1:
        raise ValidationError("At least one administrator is required")
    user_repository.delete(user_id)
    return user


def change_password(user, current_password, new_password):
    if not check_password_hash(user.password_hash, current_password or ""):
        raise AuthenticationError("The current password is incorrect")
    validate_password(new_password)
    user_repository.update(user.id, password_hash=hash_password(new_password))
