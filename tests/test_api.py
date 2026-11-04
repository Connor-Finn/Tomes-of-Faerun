"""API tests with Playwright's APIRequestContext (no browser needed).

The React app is just a client of this API, so testing the API directly is the
fastest way to cover the rules (validation, permissions, security) in depth.
"""
import pytest
from playwright.sync_api import APIRequestContext, Playwright

from conftest import unique_email

pytestmark = pytest.mark.api


def test_health(api: APIRequestContext):
    response = api.get("/api/health")
    assert response.ok
    assert response.json() == {"status": "ok"}


def test_session_is_empty_when_logged_out(api: APIRequestContext):
    assert api.get("/api/auth/session").json() == {"user": None}


def test_login_with_bad_credentials(api: APIRequestContext, user):
    response = api.post("/api/auth/login", data={"email": user["email"], "password": "nope"})
    assert response.status == 401
    assert response.json()["error"] == "Invalid email or password."


def test_login_refused_for_unverified_user(api: APIRequestContext):
    response = api.post("/api/auth/login", data={"email": "unverified@example.com", "password": "Password123!"})
    assert response.status == 403
    assert response.json()["code"] == "unverified"


def test_session_returns_logged_in_user(user_api: APIRequestContext, user):
    body = user_api.get("/api/auth/session").json()["user"]
    assert body["email"] == user["email"]
    assert body["role"] == "user"
    assert "password_hash" not in body  # never leak secrets


def test_protected_endpoints_need_login(api: APIRequestContext):
    response = api.patch("/api/account/profile", data={"name": "Nope"})
    assert response.status == 401


def test_post_without_csrf_header_is_rejected(playwright: Playwright, base_url: str, user):
    """A request with no X-Requested-With header (like a forged form post) is refused."""
    bare = playwright.request.new_context(base_url=base_url)
    try:
        response = bare.post("/api/auth/login", data={"email": user["email"], "password": user["password"]})
        assert response.status == 403
        assert "X-Requested-With" in response.json()["error"]
    finally:
        bare.dispose()


def test_signup_validation_returns_field_errors(api: APIRequestContext):
    response = api.post("/api/auth/signup", data={"name": "", "email": "bad", "password": "weak"})
    assert response.status == 400
    errors = response.json()["errors"]
    assert set(errors) >= {"name", "email", "password", "confirm_password", "experience", "terms"}


def test_signup_sends_verification_email(api: APIRequestContext):
    email = unique_email("apisignup")
    response = api.post("/api/auth/signup", data={
        "name": "Api Bard", "email": email, "password": "Str0ng!Pass", "confirm_password": "Str0ng!Pass",
        "experience": "veteran", "terms": True,
    })
    assert response.status == 201
    latest = api.get("/__test__/emails/latest", params={"to": email}).json()
    assert latest["subject"] == "Verify your Tomes of Faerun account"
    assert "/verify/" in latest["link"]


def test_profile_update_round_trip(user_api: APIRequestContext):
    response = user_api.patch("/api/account/profile", data={
        "name": "Api Paladin", "bio": "Oath of Devotion", "timezone": "Europe/London",
        "experience": "some", "notify_email": False, "notify_party": True,
    })
    assert response.ok, response.text()
    saved = user_api.get("/api/auth/session").json()["user"]
    assert saved["name"] == "Api Paladin"
    assert saved["timezone"] == "Europe/London"
    assert saved["notify_party"] is True


def test_profile_rejects_unknown_timezone(user_api: APIRequestContext):
    response = user_api.patch("/api/account/profile", data={
        "name": "Someone", "bio": "", "timezone": "Mars/Olympus_Mons", "experience": "new",
    })
    assert response.status == 400
    assert response.json()["errors"]["timezone"] == "Choose a valid time zone."


def test_logout_ends_session(user_api: APIRequestContext):
    assert user_api.post("/api/auth/logout").ok
    assert user_api.get("/api/auth/session").json() == {"user": None}


def test_unknown_api_route_returns_json_404(api: APIRequestContext):
    response = api.get("/api/does-not-exist")
    assert response.status == 404
    assert "error" in response.json()
