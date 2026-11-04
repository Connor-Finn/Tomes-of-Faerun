"""Sign up, email verification, log in/out and password reset."""
from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, g, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import EXPERIENCE_LEVELS, User, utcnow
from .security import (
    EMAIL_RE, get_user_by_email, json_body, lookup_token, make_token, name_error,
    password_error, send_email, send_verification_email, site_url, text, validation_failed,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
LOCKED_MSG = (f"Your account is locked after too many failed attempts. "
              f"Try again in {LOCKOUT_MINUTES} minutes or reset your password.")


@bp.get("/session")
def current_session():
    """Who is logged in? The React app calls this on every page load."""
    return jsonify(user=g.user.to_dict() if g.user else None)


@bp.post("/signup")
def signup():
    data = json_body()
    name, email = text(data, "name"), text(data, "email").lower()
    password, confirm = str(data.get("password") or ""), str(data.get("confirm_password") or "")
    experience = text(data, "experience")
    errors = {}

    if err := name_error(name):
        errors["name"] = err
    if not email:
        errors["email"] = "Email is required."
    elif not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    elif get_user_by_email(email):
        errors["email"] = "An account with this email already exists."
    if err := password_error(password):
        errors["password"] = err
    if not confirm:
        errors["confirm_password"] = "Please confirm your password."
    elif password != confirm:
        errors["confirm_password"] = "Passwords do not match."
    if experience not in EXPERIENCE_LEVELS:
        errors["experience"] = "Please choose your experience level."
    if not data.get("terms"):
        errors["terms"] = "You must accept the Terms of Service."
    if errors:
        return validation_failed(errors)

    user = User(name=name, email=email, password_hash=generate_password_hash(password),
                experience=experience, newsletter=bool(data.get("newsletter")))
    db.session.add(user)
    db.session.flush()
    send_verification_email(user)
    db.session.commit()
    return jsonify(email=email), 201


@bp.post("/verify")
def verify_email():
    row = lookup_token(text(json_body(), "token"), "verify")
    if row is None:
        return jsonify(error="This verification link is invalid or has expired."), 400
    row.user.is_verified = True
    row.used = True
    db.session.commit()
    return jsonify(message="Your email has been verified. You can now log in.")


@bp.post("/resend-verification")
def resend_verification():
    email = text(json_body(), "email").lower()
    user = get_user_by_email(email) if email else None
    if user and not user.is_verified:
        send_verification_email(user)
        db.session.commit()
    # Same answer whether or not the account exists (don't leak which emails are registered).
    return jsonify(message="If that account exists and is unverified, a new verification email has been sent.")


@bp.post("/login")
def login():
    data = json_body()
    email, password = text(data, "email").lower(), str(data.get("password") or "")
    user = get_user_by_email(email) if email else None
    now = utcnow()

    if user and user.locked_until and user.locked_until > now:
        return jsonify(error=LOCKED_MSG, code="locked"), 401
    if user is None or not check_password_hash(user.password_hash, password):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILED_LOGINS:
                user.failed_logins = 0
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                db.session.commit()
                return jsonify(error=LOCKED_MSG, code="locked"), 401
            db.session.commit()
        # Same message for unknown emails and wrong passwords.
        return jsonify(error="Invalid email or password.", code="invalid"), 401
    if user.is_banned:
        return jsonify(error="This account has been suspended. Contact support.", code="banned"), 403
    if not user.is_verified:
        return jsonify(error="Please verify your email address before logging in.", code="unverified"), 403

    user.failed_logins, user.locked_until, user.last_login = 0, None, now
    db.session.commit()
    session.clear()
    session["user_id"] = user.id
    session.permanent = bool(data.get("remember"))
    return jsonify(user=user.to_dict())


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify(message="You have been logged out.")


@bp.post("/forgot-password")
def forgot_password():
    email = text(json_body(), "email").lower()
    if not EMAIL_RE.match(email):
        return validation_failed({"email": "Enter a valid email address."})
    user = get_user_by_email(email)
    if user:
        token = make_token(user, "reset", hours=1)
        send_email(user.email, "Reset your Tomes of Faerun password",
                   f"Greetings {user.name},\n\nSomeone asked to reset your password. "
                   "If that was you, open the link below (valid for 1 hour). "
                   "Otherwise you can ignore this email.",
                   site_url(f"/reset-password/{token}"))
        db.session.commit()
    return jsonify(message="If an account exists for that email, we've sent a password reset link.")


@bp.get("/reset-password/<token>")
def check_reset_token(token):
    if lookup_token(token, "reset") is None:
        return jsonify(error="This reset link is invalid or has expired."), 400
    return jsonify(valid=True)


@bp.post("/reset-password/<token>")
def reset_password(token):
    row = lookup_token(token, "reset")
    if row is None:
        return jsonify(error="This reset link is invalid or has expired."), 400
    data = json_body()
    password, confirm = str(data.get("password") or ""), str(data.get("confirm_password") or "")
    errors = {}
    if err := password_error(password):
        errors["password"] = err
    if password != confirm:
        errors["confirm_password"] = "Passwords do not match."
    if errors:
        return validation_failed(errors)
    user = row.user
    user.password_hash = generate_password_hash(password)
    user.failed_logins, user.locked_until = 0, None
    row.used = True
    db.session.commit()
    return jsonify(message="Your password has been reset. Please log in with your new password.")
