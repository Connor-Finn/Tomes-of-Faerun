"""Developer tools: the fake mailbox and test-only helper routes.

These exist so end-to-end tests can read "sent" emails and set up data quickly.
They are switched off with DEV_TOOLS=0 and must never be enabled in production.
"""
from flask import Blueprint, abort, current_app, jsonify, request
from sqlalchemy import delete, select
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import Email, User
from .security import EMAIL_RE, get_user_by_email

bp = Blueprint("dev", __name__)


@bp.before_request
def only_when_enabled():
    if not current_app.config["DEV_TOOLS"]:
        abort(404)


@bp.get("/api/dev/mailbox")
def mailbox():
    to = request.args.get("to", "").strip().lower()
    stmt = select(Email).order_by(Email.id.desc()).limit(50)
    if to:
        stmt = stmt.where(Email.to_addr == to)
    return jsonify(emails=[e.to_dict() for e in db.session.scalars(stmt)])


@bp.delete("/api/dev/mailbox")
def clear_mailbox():
    db.session.execute(delete(Email))
    db.session.commit()
    return jsonify(message="Mailbox cleared.")


@bp.post("/__test__/reset")
def reset():
    from .seed import reset_database
    reset_database()
    return jsonify(status="reset")


@bp.post("/__test__/users")
def create_user():
    """Create a user directly, skipping signup and email verification. Fast test setup."""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    if not EMAIL_RE.match(email):
        return jsonify(error="A valid email is required."), 400
    if get_user_by_email(email):
        return jsonify(error="User already exists."), 409
    user = User(
        name=data.get("name", "Test Adventurer"), email=email,
        password_hash=generate_password_hash(data.get("password", "Password123!")),
        role=data.get("role", "user"), is_verified=data.get("verified", True),
        is_banned=data.get("banned", False), experience=data.get("experience", "new"),
    )
    db.session.add(user)
    db.session.commit()
    return jsonify(id=user.id, email=email), 201


@bp.get("/__test__/emails/latest")
def latest_email():
    to = request.args.get("to", "").strip().lower()
    row = db.session.scalar(select(Email).where(Email.to_addr == to).order_by(Email.id.desc()).limit(1))
    if row is None:
        return jsonify(error=f"No email found for {to}."), 404
    return jsonify(row.to_dict())
