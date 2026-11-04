"""Create the database and fill it with demo accounts."""
import shutil
from pathlib import Path

from flask import current_app
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import User

SEED_USERS = [
    dict(name="Elminster Aumar", email="admin@example.com", password="Admin123!", role="admin", experience="veteran"),
    dict(name="Test Adventurer", email="user@example.com", password="Password123!", experience="some"),
    dict(name="Banned Bandit", email="banned@example.com", password="Password123!", banned=True),
    dict(name="Unverified Wanderer", email="unverified@example.com", password="Password123!", verified=False),
]


def seed() -> None:
    for u in SEED_USERS:
        db.session.add(User(
            name=u["name"], email=u["email"], password_hash=generate_password_hash(u["password"]),
            role=u.get("role", "user"), experience=u.get("experience", "new"),
            is_verified=u.get("verified", True), is_banned=u.get("banned", False),
        ))
    db.session.commit()


def reset_database() -> None:
    """Drop everything, recreate the tables, add the seed data and delete uploads."""
    db.session.remove()
    db.drop_all()
    db.create_all()
    uploads = Path(current_app.config["UPLOAD_FOLDER"])
    shutil.rmtree(uploads, ignore_errors=True)
    uploads.mkdir(parents=True, exist_ok=True)
    seed()


def ensure_database() -> None:
    db_path = Path(db.engine.url.database)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not inspect(db.engine).has_table("users"):
        reset_database()
