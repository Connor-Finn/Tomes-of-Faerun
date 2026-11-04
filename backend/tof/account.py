"""Account management: profile, avatar, password change and account deletion."""
from __future__ import annotations

import secrets
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import EXPERIENCE_LEVELS, TIMEZONES
from .security import json_body, login_required, name_error, password_error, send_email, text, validation_failed

bp = Blueprint("account", __name__)

MAX_AVATAR_BYTES = 1024 * 1024
ALLOWED_AVATAR_EXT = {"png", "jpg", "jpeg", "gif"}


@bp.get("/api/account/options")
def options():
    """Choices for the profile and signup forms, so the front end never hard-codes them."""
    return jsonify(
        experience_levels=[{"value": k, "label": v} for k, v in EXPERIENCE_LEVELS.items()],
        timezones=TIMEZONES,
    )


@bp.patch("/api/account/profile")
@login_required
def update_profile():
    data = json_body()
    form = {
        "name": text(data, "name"),
        "bio": text(data, "bio"),
        "timezone": text(data, "timezone"),
        "experience": text(data, "experience"),
    }
    errors = {}
    if err := name_error(form["name"]):
        errors["name"] = err
    if len(form["bio"]) > 200:
        errors["bio"] = "Bio must be 200 characters or fewer."
    if form["timezone"] not in TIMEZONES:
        errors["timezone"] = "Choose a valid time zone."
    if form["experience"] not in EXPERIENCE_LEVELS:
        errors["experience"] = "Choose a valid experience level."
    if errors:
        return validation_failed(errors)
    user = g.user
    for key, value in form.items():
        setattr(user, key, value)
    user.notify_email = bool(data.get("notify_email"))
    user.notify_party = bool(data.get("notify_party"))
    db.session.commit()
    return jsonify(user=user.to_dict(), message="Profile updated successfully.")


def _upload_dir() -> Path:
    return Path(current_app.config["UPLOAD_FOLDER"])


def _delete_avatar_file(filename: str | None) -> None:
    if filename and (path := _upload_dir() / filename).is_file():
        path.unlink()


@bp.post("/api/account/avatar")
@login_required
def upload_avatar():
    file = request.files.get("avatar")
    if file is None or not file.filename:
        return jsonify(error="Please choose a file to upload."), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_AVATAR_EXT:
        return jsonify(error="Avatar must be a PNG, JPG or GIF image."), 400
    data = file.read()
    if len(data) > MAX_AVATAR_BYTES:
        return jsonify(error="Avatar must be smaller than 1 MB."), 400
    filename = f"user{g.user.id}_{secrets.token_hex(4)}.{ext}"
    _upload_dir().mkdir(parents=True, exist_ok=True)
    (_upload_dir() / filename).write_bytes(data)
    _delete_avatar_file(g.user.avatar)
    g.user.avatar = filename
    db.session.commit()
    return jsonify(user=g.user.to_dict(), message="Avatar updated.")


@bp.delete("/api/account/avatar")
@login_required
def remove_avatar():
    _delete_avatar_file(g.user.avatar)
    g.user.avatar = None
    db.session.commit()
    return jsonify(user=g.user.to_dict(), message="Avatar removed.")


@bp.get("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(_upload_dir(), filename)


@bp.post("/api/account/password")
@login_required
def change_password():
    data = json_body()
    current = str(data.get("current_password") or "")
    new = str(data.get("new_password") or "")
    confirm = str(data.get("confirm_password") or "")
    errors = {}
    if not check_password_hash(g.user.password_hash, current):
        errors["current_password"] = "Current password is incorrect."
    if err := password_error(new):
        errors["new_password"] = err
    elif new == current:
        errors["new_password"] = "New password must be different from your current password."
    if new != confirm:
        errors["confirm_password"] = "Passwords do not match."
    if errors:
        return validation_failed(errors)
    g.user.password_hash = generate_password_hash(new)
    send_email(g.user.email, "Your Tomes of Faerun password was changed",
               "Your password was just changed. If this wasn't you, reset your password immediately.")
    db.session.commit()
    return jsonify(message="Password changed successfully.")


@bp.delete("/api/account")
@login_required
def delete_account():
    data = json_body()
    if data.get("confirm_text") != "DELETE":
        return jsonify(error="Account not deleted: you must type DELETE to confirm."), 400
    if not check_password_hash(g.user.password_hash, str(data.get("password") or "")):
        return jsonify(error="Account not deleted: incorrect password."), 400
    _delete_avatar_file(g.user.avatar)
    db.session.delete(g.user)
    db.session.commit()
    session.clear()
    return jsonify(message="Your account has been permanently deleted.")
