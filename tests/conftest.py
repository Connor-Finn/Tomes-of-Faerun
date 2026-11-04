"""
Shared pytest fixtures.

Key ideas shown here (all common in real QA jobs):
  * live_server   - starts the Flask API (which also serves the built React app)
                    in a subprocess with its OWN throwaway database
  * base_url      - lets tests call page.goto("/login") instead of full URLs
  * api           - Playwright's APIRequestContext for fast, browser-less HTTP calls
  * create_user   - makes a unique user per test, so tests never share state
                    (which is what makes running them in parallel safe)
  * logged_in_page / admin_page - skip the login UI when it isn't what you're testing
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest
from playwright.sync_api import APIRequestContext, Browser, Page, Playwright, expect

from pages import LoginPage

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Every state-changing API call must carry this header (it's the app's CSRF protection).
API_HEADERS = {"X-Requested-With": "pytest"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server(tmp_path_factory) -> str:
    """Start the app on a random free port with a fresh database.

    Set TOMES_URL=http://127.0.0.1:5000 to test an already-running server instead.
    """
    external = os.environ.get("TOMES_URL")
    if external:
        yield external.rstrip("/")
        return

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.exit("The React app isn't built. Run `npm run build` in frontend/ first.", returncode=1)

    port = _free_port()
    workdir = tmp_path_factory.mktemp("tomes")
    log_path = workdir / "server.log"
    env = {
        **os.environ,
        "PORT": str(port),
        "DATABASE": str(workdir / "test.db"),
        "DEV_TOOLS": "1",
        "FLASK_DEBUG": "0",
        "PYTHONUNBUFFERED": "1",
    }
    with open(log_path, "w") as log:
        proc = subprocess.Popen([sys.executable, "run.py"], env=env, cwd=BACKEND,
                                stdout=log, stderr=subprocess.STDOUT)
        url = f"http://127.0.0.1:{port}"
        deadline = time.time() + 30
        while True:
            try:
                with urllib.request.urlopen(f"{url}/api/health", timeout=1):
                    break
            except OSError:
                if proc.poll() is not None or time.time() > deadline:
                    proc.kill()
                    raise RuntimeError(f"The app failed to start:\n{log_path.read_text()}")
                time.sleep(0.2)
        yield url
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def base_url(live_server: str) -> str:
    # Overrides pytest-base-url's fixture; pytest-playwright passes it to every browser context.
    return live_server


@pytest.fixture(scope="session")
def api(playwright: Playwright, base_url: str) -> APIRequestContext:
    """Logged-out API client (no browser involved)."""
    ctx = playwright.request.new_context(base_url=base_url, extra_http_headers=API_HEADERS)
    yield ctx
    ctx.dispose()


@pytest.fixture(scope="session", autouse=True)
def fresh_database(api: APIRequestContext) -> None:
    """Reset + re-seed the DB once at the start of the test session."""
    response = api.post("/__test__/reset")
    assert response.ok, f"Reset failed ({response.status}). Is DEV_TOOLS=1?"


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------
def unique_email(prefix: str = "user") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
def create_user(api: APIRequestContext):
    """Factory fixture: create_user(role="admin", verified=False, ...) -> dict."""
    def _create(**overrides) -> dict:
        data = {
            "name": "Test Adventurer",
            "email": unique_email(),
            "password": "Password123!",
            "verified": True,
        }
        data.update(overrides)
        response = api.post("/__test__/users", data=data)
        assert response.status == 201, response.text()
        return {**data, "id": response.json()["id"]}
    return _create


@pytest.fixture
def user(create_user) -> dict:
    """A brand-new verified user for this test only."""
    return create_user()


@pytest.fixture
def user_api(playwright: Playwright, base_url: str, user: dict) -> APIRequestContext:
    """API client logged in as `user`. It keeps the session cookie like a browser would."""
    ctx = playwright.request.new_context(base_url=base_url, extra_http_headers=API_HEADERS)
    response = ctx.post("/api/auth/login", data={"email": user["email"], "password": user["password"]})
    assert response.ok, response.text()
    yield ctx
    ctx.dispose()


@pytest.fixture
def other_api(playwright: Playwright, base_url: str, create_user) -> APIRequestContext:
    """A second, unrelated player, for checking that nobody can see or change your things."""
    someone = create_user()
    ctx = playwright.request.new_context(base_url=base_url, extra_http_headers=API_HEADERS)
    assert ctx.post("/api/auth/login", data={"email": someone["email"], "password": someone["password"]}).ok
    yield ctx
    ctx.dispose()


# ---------------------------------------------------------------------------
# Logged-in pages
# ---------------------------------------------------------------------------
@pytest.fixture
def logged_in_page(page: Page, user: dict) -> Page:
    """A page already logged in as `user` (through the real login form)."""
    LoginPage(page).open().login(user["email"], user["password"])
    expect(page).to_have_url(re.compile(r"/guild-hall$"))
    return page


@pytest.fixture(scope="session")
def admin_storage_state(browser: Browser, browser_context_args: dict, tmp_path_factory) -> Path:
    """Log in as admin ONCE per session and save the cookies to a file.

    This is Playwright's "storage state" pattern: big suites log in once and
    reuse the session instead of typing credentials in every test.
    """
    context = browser.new_context(**browser_context_args)
    page = context.new_page()
    LoginPage(page).open().login("admin@example.com", "Admin123!")
    expect(page).to_have_url(re.compile(r"/guild-hall$"))
    path = tmp_path_factory.mktemp("auth") / "admin.json"
    context.storage_state(path=path)
    context.close()
    return path


@pytest.fixture
def admin_page(browser: Browser, browser_context_args: dict, admin_storage_state: Path) -> Page:
    context = browser.new_context(**browser_context_args, storage_state=admin_storage_state)
    page = context.new_page()
    yield page
    context.close()
