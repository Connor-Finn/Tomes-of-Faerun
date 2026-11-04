import os
from datetime import timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
DATABASE = os.environ.get("DATABASE", str(BACKEND_DIR / "instance" / "tomes.db"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE}"
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(Path(DATABASE).parent / "uploads"))
    FRONTEND_DIST = os.environ.get("FRONTEND_DIST", str(REPO_DIR / "frontend" / "dist"))
    # Dev tools = the fake mailbox and the /__test__ helper routes.
    # They let tests reset data and read emails. NEVER enable them in production.
    DEV_TOOLS = os.environ.get("DEV_TOOLS", "1") == "1"
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True
