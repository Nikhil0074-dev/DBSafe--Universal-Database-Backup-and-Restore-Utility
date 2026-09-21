from flask import Blueprint, redirect, render_template, url_for

from ..exceptions import NotFoundError
from ..repositories import database_repository
from .security import current_user, page_login_required

bp = Blueprint("pages", __name__)


@bp.get("/login")
def login():
    if current_user():
        return redirect(url_for("pages.dashboard"))
    return render_template("login.html")


@bp.get("/")
@page_login_required()
def dashboard():
    return render_template("dashboard.html")


@bp.get("/databases")
@page_login_required()
def databases():
    return render_template("databases.html")


@bp.get("/databases/add")
@page_login_required("admin")
def add_database():
    return render_template("add_database.html", connection_id=None)


@bp.get("/databases/<int:connection_id>/edit")
@page_login_required("admin")
def edit_database(connection_id):
    if database_repository.get(connection_id) is None:
        raise NotFoundError("Database connection not found")
    return render_template("add_database.html", connection_id=connection_id)


@bp.get("/backups")
@page_login_required()
def backups():
    return render_template("backups.html")


@bp.get("/backups/<int:backup_id>")
@page_login_required()
def backup_details(backup_id):
    return render_template("backup_details.html", backup_id=backup_id)


@bp.get("/restore")
@page_login_required()
def restore():
    return render_template("restore.html")


@bp.get("/schedules")
@page_login_required()
def schedules():
    return render_template("schedules.html")


@bp.get("/storage")
@page_login_required()
def storage():
    return render_template("storage.html")


@bp.get("/logs")
@page_login_required("admin")
def logs():
    return render_template("logs.html")


@bp.get("/users")
@page_login_required("admin")
def users():
    return render_template("users.html")


@bp.get("/account")
@page_login_required()
def account():
    return render_template("account.html")
