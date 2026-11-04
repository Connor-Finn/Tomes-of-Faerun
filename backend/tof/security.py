"""Shared helpers: current user, access control, validation, tokens and email."""
from __future__ import annotations

import re
import secrets
from datetime import timedelta
from functools import wraps

from flask import abort, g, request, session
from sqlalchemy import select, update

from .extensions import db
from .models import Email, Token, User, utcnow

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
CSRF_HEADER = "X-Requested-With"


# ---------------------------------------------------------------------------
# Request hooks
# ---------------------------------------------------------------------------
def load_current_user() -> None:
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return
    user = db.session.get(User, user_id)
    if user is None or user.is_banned:
        session.pop("user_id", None)  # deleted or banned users are logged out
    else:
        g.user = user


def require_csrf_header():
    """CSRF protection for a JSON API that uses cookie sessions.

    Every state-changing /api/ request must send a custom header. Browsers
    won't let another website add custom headers to a cross-site request
    (without a CORS preflight, which we never allow), so a forged form post
    from evil.example.com is rejected.
    """
    if request.method in ("GET", "HEAD", "OPTIONS") or not request.path.startswith("/api/"):
        return None
    if not request.headers.get(CSRF_HEADER):
        abort(403, description=f"Missing {CSRF_HEADER} header.")
    return None


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            abort(401, description="Please log in to continue.")
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            abort(401, description="Please log in to continue.")
        if not g.user.is_admin:
            abort(403, description="You don't have permission to do that.")
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Request body must be a JSON object.")
    return data


def text(data: dict, key: str) -> str:
    return str(data.get(key) or "").strip()


def password_problems(pw: str) -> list[str]:
    problems = []
    if len(pw) < 8:
        problems.append("at least 8 characters")
    if not re.search(r"[A-Z]", pw):
        problems.append("an uppercase letter")
    if not re.search(r"[a-z]", pw):
        problems.append("a lowercase letter")
    if not re.search(r"\d", pw):
        problems.append("a number")
    if not re.search(r"[^A-Za-z0-9]", pw):
        problems.append("a special character")
    return problems


def password_error(pw: str) -> str | None:
    problems = password_problems(pw)
    return f"Password must contain {', '.join(problems)}." if problems else None


def name_error(name: str) -> str | None:
    if not name:
        return "Name is required."
    if len(name) > 50:
        return "Name must be 50 characters or fewer."
    return None


def validation_failed(errors: dict):
    return {"error": "Please fix the highlighted fields.", "errors": errors}, 400


def get_user_by_email(email: str) -> User | None:
    return db.session.scalar(select(User).where(User.email == email.strip().lower()))


# ---------------------------------------------------------------------------
# One-time tokens and (fake) email
# ---------------------------------------------------------------------------
def make_token(user: User, kind: str, hours: int) -> str:
    # Only the newest verify/reset link works.
    db.session.execute(
        update(Token).where(Token.user_id == user.id, Token.kind == kind, Token.used.is_(False)).values(used=True)
    )
    value = secrets.token_urlsafe(32)
    db.session.add(Token(user_id=user.id, kind=kind, token=value, expires_at=utcnow() + timedelta(hours=hours)))
    return value


def lookup_token(value: str, kind: str) -> Token | None:
    row = db.session.scalar(select(Token).where(Token.token == value, Token.kind == kind))
    if row is None or row.used or row.expires_at < utcnow():
        return None
    return row


def send_email(to: str, subject: str, body: str, link: str | None = None) -> None:
    """Fake email: stored in the database and visible in the dev mailbox."""
    db.session.add(Email(to_addr=to, subject=subject, body=body, link=link))


def site_url(path: str) -> str:
    return request.host_url.rstrip("/") + path


def send_verification_email(user: User) -> None:
    token = make_token(user, "verify", hours=24)
    send_email(
        user.email,
        "Verify your Tomes of Faerun account",
        f"Greetings {user.name},\n\nPlease confirm your email address by opening the link below. "
        "It expires in 24 hours.",
        site_url(f"/verify/{token}"),
    )
