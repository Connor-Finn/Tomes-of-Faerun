"""Tomes of Faerun: the Flask API that powers the React front end.

The app is split into blueprints, one per area of the product:

    auth     sign up, email verification, log in/out, password reset
    account  profile, avatar, password change, account deletion
    admin    user management (admins only)
    dev      fake mailbox and test-only helpers (never enabled in production)
    rules    read-only D&D 5e SRD content: spells, monsters, classes, items...
    characters  the Character Manager: rules-checked character builds and sheets
    bestiary the DM's monster collections and environments
    spa      serves the built React app for every non-API URL
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import db


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app)

    from . import account, admin, auth, bestiary, dev, spa
    from .characters import api as characters_api
    from .rules import api as rules_api
    from .security import load_current_user, require_csrf_header

    app.before_request(load_current_user)
    app.before_request(require_csrf_header)

    app.register_blueprint(auth.bp)
    app.register_blueprint(account.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(dev.bp)
    app.register_blueprint(rules_api.bp)
    app.register_blueprint(characters_api.bp)
    app.register_blueprint(bestiary.bp)
    app.register_blueprint(spa.bp)  # last: it catches every other URL

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(HTTPException)
    def http_error(e: HTTPException):
        if request.path.startswith(("/api/", "/__test__/")):
            return jsonify(error=e.description), e.code
        return e

    with app.app_context():
        from .seed import ensure_database
        ensure_database()

    return app
