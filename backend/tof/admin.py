"""User management for admins (role-based access control)."""
from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import or_, select

from .extensions import db
from .models import User
from .security import admin_required

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _get_other_user(user_id: int, action: str) -> User:
    if user_id == g.user.id:
        abort(400, description=f"You cannot {action} yourself.")
    return db.session.get(User, user_id) or abort(404, description="User not found.")


@bp.get("/users")
@admin_required
def list_users():
    q = request.args.get("q", "").strip()
    stmt = select(User).order_by(User.id)
    if q:
        stmt = stmt.where(or_(User.name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    return jsonify(users=[u.to_dict() for u in db.session.scalars(stmt)])


@bp.post("/users/<int:user_id>/toggle-ban")
@admin_required
def toggle_ban(user_id):
    user = _get_other_user(user_id, "ban")
    user.is_banned = not user.is_banned
    db.session.commit()
    verb = "banned" if user.is_banned else "unbanned"
    return jsonify(user=user.to_dict(), message=f"{user.email} has been {verb}.")


@bp.post("/users/<int:user_id>/toggle-role")
@admin_required
def toggle_role(user_id):
    user = _get_other_user(user_id, "change the role of")
    user.role = "user" if user.is_admin else "admin"
    db.session.commit()
    what = "an admin" if user.is_admin else "a regular user"
    return jsonify(user=user.to_dict(), message=f"{user.email} is now {what}.")
