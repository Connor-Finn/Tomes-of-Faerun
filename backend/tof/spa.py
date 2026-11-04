"""Serve the built React app. Any URL that isn't an API route gets index.html,
so React Router can handle /login, /account/profile and so on."""
from pathlib import Path

from flask import Blueprint, abort, current_app, send_from_directory

bp = Blueprint("spa", __name__)


@bp.get("/", defaults={"path": ""})
@bp.get("/<path:path>")
def frontend(path: str):
    if path.startswith(("api/", "__test__/")):
        abort(404)
    dist = Path(current_app.config["FRONTEND_DIST"])
    if not (dist / "index.html").is_file():
        return ("The front end hasn't been built yet. Run `npm run build` in frontend/, "
                "or use `npm run dev` and open http://localhost:5173."), 503
    if path and (dist / path).is_file():
        return send_from_directory(dist, path)
    return send_from_directory(dist, "index.html")
