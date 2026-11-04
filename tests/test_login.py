"""Login, logout, lockout, redirects, remember-me and password reset."""
import re
import time

from playwright.sync_api import APIRequestContext, Page, expect

from pages import LoginPage


def test_login_success(page: Page, user):
    LoginPage(page).open().login(user["email"], user["password"])
    expect(page).to_have_url(re.compile(r"/dashboard$"))
    expect(page.get_by_test_id("flash-success")).to_have_text(f"Welcome back, {user['name']}!")
    expect(page.get_by_test_id("user-menu-button")).to_contain_text(user["name"])


def test_login_wrong_password_shows_generic_error(page: Page, user):
    login = LoginPage(page).open().login(user["email"], "WrongPassword1!")
    expect(login.error).to_have_text("Invalid email or password.")
    expect(page).to_have_url(re.compile(r"/login"))


def test_login_unknown_email_shows_same_error(page: Page):
    # Same message as a wrong password, so attackers can't discover which emails exist.
    login = LoginPage(page).open().login("nobody@example.com", "Whatever1!")
    expect(login.error).to_have_text("Invalid email or password.")


def test_browser_blocks_empty_required_field(page: Page):
    """The login form uses native HTML5 validation, so the browser blocks the submit."""
    login = LoginPage(page).open()
    login.submit.click()
    expect(page).to_have_url(re.compile(r"/login$"))
    message = login.email.evaluate("el => el.validationMessage")
    assert message, "expected the browser to show a validation message"


def test_account_locks_after_five_failed_attempts(page: Page, user):
    login = LoginPage(page).open()
    for _ in range(4):
        login.login(user["email"], "WrongPassword1!")
        expect(login.error).to_have_text("Invalid email or password.")
    login.login(user["email"], "WrongPassword1!")
    expect(login.error).to_contain_text("Your account is locked")

    # Even the correct password is refused while locked.
    login.login(user["email"], user["password"])
    expect(login.error).to_contain_text("Your account is locked")


def test_banned_user_cannot_log_in(page: Page):
    login = LoginPage(page).open().login("banned@example.com", "Password123!")
    expect(login.error).to_have_text("This account has been suspended. Contact support.")


def test_unverified_seed_user_cannot_log_in(page: Page):
    login = LoginPage(page).open().login("unverified@example.com", "Password123!")
    expect(login.error).to_have_text("Please verify your email address before logging in.")
    expect(page.get_by_role("button", name="Resend verification email")).to_be_visible()


def test_logged_in_user_is_sent_from_login_to_dashboard(logged_in_page: Page):
    logged_in_page.goto("/login")
    expect(logged_in_page).to_have_url(re.compile(r"/dashboard$"))


def test_session_survives_a_page_reload(logged_in_page: Page, user):
    """The React app asks the API who is logged in on every load."""
    logged_in_page.reload()
    expect(logged_in_page.get_by_test_id("user-menu-button")).to_contain_text(user["name"])


def test_logout(logged_in_page: Page):
    page = logged_in_page
    page.get_by_test_id("user-menu-button").click()
    page.get_by_role("menuitem", name="Log out").click()
    expect(page).to_have_url(re.compile(r"/login$"))
    expect(page.get_by_test_id("flash-info")).to_have_text("You have been logged out.")

    # The session is really gone: protected pages bounce back to login,
    # even after a full page load.
    page.goto("/dashboard")
    expect(page).to_have_url(re.compile(r"/login\?next="))


def test_protected_page_redirects_to_login_then_back(page: Page, user):
    page.goto("/account/security?tab=password")
    expect(page).to_have_url(re.compile(r"/login\?next="))
    expect(page.get_by_test_id("flash-warning")).to_have_text("Please log in to access that page.")

    LoginPage(page).login(user["email"], user["password"])
    expect(page).to_have_url(re.compile(r"/account/security\?tab=password$"))


def test_open_redirect_is_blocked(page: Page, user):
    """Security check: ?next= must not send users to another website."""
    LoginPage(page).open(next_path="https://evil.example.com").login(user["email"], user["password"])
    expect(page).to_have_url(re.compile(r"/dashboard$"))


def test_remember_me_sets_persistent_cookie(page: Page, user):
    LoginPage(page).open().login(user["email"], user["password"], remember=True)
    expect(page).to_have_url(re.compile(r"/dashboard$"))
    session_cookie = next(c for c in page.context.cookies() if c["name"] == "session")
    assert session_cookie["expires"] > time.time() + 29 * 24 * 3600  # ~30 days


def test_without_remember_me_cookie_is_session_only(page: Page, user):
    LoginPage(page).open().login(user["email"], user["password"])
    expect(page).to_have_url(re.compile(r"/dashboard$"))
    session_cookie = next(c for c in page.context.cookies() if c["name"] == "session")
    assert session_cookie["expires"] == -1  # deleted when the browser closes


def test_password_reset_flow(page: Page, api: APIRequestContext, user):
    login = LoginPage(page).open()
    login.forgot_password_link.click()
    page.get_by_label("Email").fill(user["email"])
    page.get_by_role("button", name="Send reset link").click()
    expect(page.get_by_test_id("forgot-confirmation")).to_contain_text("we've sent a password reset link")

    # Grab the link via the API instead of clicking through the mailbox UI (faster).
    email = api.get("/__test__/emails/latest", params={"to": user["email"]}).json()
    assert email["subject"] == "Reset your Tomes of Faerun password"
    page.goto(email["link"])

    page.get_by_label("New password", exact=True).fill("BrandNew1!")
    page.get_by_label("Confirm new password").fill("BrandNew1!")
    page.get_by_role("button", name="Reset password").click()
    expect(page.get_by_test_id("flash-success")).to_contain_text("Your password has been reset")

    login.login(user["email"], "BrandNew1!")
    expect(page).to_have_url(re.compile(r"/dashboard$"))

    # The reset link only works once.
    page.goto(email["link"])
    expect(page.get_by_test_id("reset-invalid")).to_be_visible()


def test_forgot_password_does_not_reveal_unknown_email(page: Page):
    page.goto("/forgot-password")
    page.get_by_label("Email").fill("ghost@example.com")
    page.get_by_role("button", name="Send reset link").click()
    expect(page.get_by_test_id("forgot-confirmation")).to_be_visible()
