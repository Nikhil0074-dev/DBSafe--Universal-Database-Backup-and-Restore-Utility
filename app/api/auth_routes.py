from flask import Blueprint, jsonify, request, session

from ..repositories import log_repository
from ..services import auth_service
from ..utils.validation import clean_str
from .security import admin_required, csrf_token, current_user, json_body, login_required

bp = Blueprint("auth", __name__, url_prefix="/api")


@bp.get("/auth/csrf")
def get_csrf():
    return jsonify(csrf_token=csrf_token())


@bp.post("/auth/login")
def login():
    data = json_body()
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    try:
        user = auth_service.authenticate(username, password, request.remote_addr)
    except Exception as exc:
        log_repository.add("login", "failed", f"Failed login for '{username[:64]}'", None, None)
        raise exc
    session.clear()  # prevent session fixation
    session["user_id"] = user.id
    session.permanent = True
    token = csrf_token()
    log_repository.add("login", "success", f"{user.username} logged in", None,
                       {"id": user.id, "username": user.username})
    return jsonify(user=user.to_dict(), csrf_token=token)


@bp.post("/auth/logout")
def logout():
    user = current_user()
    if user:
        log_repository.add("logout", "success", f"{user['username']} logged out", None, user)
    session.clear()
    return jsonify(ok=True)


@bp.get("/auth/me")
@login_required
def me():
    return jsonify(user=current_user())


@bp.post("/auth/change-password")
@login_required
def change_password():
    data = json_body()
    user = auth_service.user_repository.get(current_user()["id"])
    auth_service.change_password(user, str(data.get("current_password") or ""),
                                 str(data.get("new_password") or ""))
    log_repository.add("change_password", "success", "Password changed", None, current_user())
    return jsonify(ok=True)


@bp.get("/users")
@admin_required
def list_users():
    return jsonify(items=[u.to_dict() for u in auth_service.user_repository.list_users()])


@bp.post("/users")
@admin_required
def create_user():
    data = json_body()
    user = auth_service.create_user(clean_str(data, "username", max_len=64),
                                    str(data.get("password") or ""),
                                    str(data.get("role") or "operator"))
    log_repository.add("create_user", "success", f"Created user {user.username} ({user.role})",
                       None, current_user())
    return jsonify(user.to_dict()), 201


@bp.put("/users/<int:user_id>")
@admin_required
def update_user(user_id):
    data = json_body()
    user = auth_service.update_user(user_id, role=data.get("role"),
                                    password=data.get("password") or None,
                                    acting_user_id=current_user()["id"])
    log_repository.add("update_user", "success", f"Updated user {user.username}", None, current_user())
    return jsonify(user.to_dict())


@bp.delete("/users/<int:user_id>")
@admin_required
def delete_user(user_id):
    user = auth_service.delete_user(user_id, current_user()["id"])
    log_repository.add("delete_user", "success", f"Deleted user {user.username}", None, current_user())
    return jsonify(ok=True)
