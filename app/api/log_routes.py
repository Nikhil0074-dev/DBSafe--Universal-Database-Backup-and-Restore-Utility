from flask import Blueprint, jsonify, request

from ..repositories import log_repository
from .security import admin_required

bp = Blueprint("logs", __name__, url_prefix="/api")


@bp.get("/logs")
@admin_required
def logs():
    args = request.args
    try:
        page = int(args.get("page", 1))
        per_page = int(args.get("per_page", 50))
    except ValueError:
        page, per_page = 1, 50
    items, total = log_repository.search(
        q=(args.get("q") or "").strip() or None, status=args.get("status") or None,
        operation=args.get("operation") or None, page=page, per_page=per_page)
    return jsonify(items=[i.to_dict() for i in items], total=total, page=page,
                   per_page=max(1, min(per_page, 200)))
