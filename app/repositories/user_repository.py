from ..models.user import User
from . import base


def count():
    return base.fetch_one("SELECT COUNT(*) AS n FROM users")["n"]


def get(user_id):
    return User.from_row(base.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,)))


def get_by_username(username):
    return User.from_row(base.fetch_one("SELECT * FROM users WHERE username = ?", (username,)))


def list_users():
    return [User.from_row(r) for r in base.fetch_all("SELECT * FROM users ORDER BY username")]


def create(username, password_hash, role):
    return base.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, password_hash, role))


def update(user_id, **fields):
    base.update_row("users", user_id, fields, {"password_hash", "role"})


def delete(user_id):
    return base.execute_count("DELETE FROM users WHERE id = ?", (user_id,))


def count_admins():
    return base.fetch_one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")["n"]
