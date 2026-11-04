"""Sign-up: happy path end to end, plus validation (negative) tests."""
import re

import pytest
from playwright.sync_api import Page, expect

from conftest import unique_email
from pages import LoginPage, SignupPage


def test_signup_verify_email_and_login(page: Page):
    """Full journey: sign up -> 'check email' -> open email -> verify -> log in."""
    email = unique_email("signup")

    SignupPage(page).open().fill(name="Jane Tester", email=email, password="Str0ng!Pass").submit.click()

    expect(page).to_have_url(re.compile(r"/signup/check-email"))
    expect(page.get_by_role("heading", name="Check your email")).to_be_visible()
    expect(page.get_by_test_id("check-email-message")).to_contain_text(email)

    # Read the verification email from the fake inbox.
    page.goto(f"/mailbox?to={email}")
    message = page.get_by_test_id("email").filter(has_text="Verify your Tomes of Faerun account")
    expect(message).to_have_count(1)
    message.get_by_test_id("email-link").click()

    expect(page.get_by_test_id("flash-success")).to_have_text("Your email has been verified. You can now log in.")
    LoginPage(page).login(email, "Str0ng!Pass")
    expect(page.get_by_role("heading", name="Welcome, Jane Tester")).to_be_visible()


def test_unverified_signup_cannot_log_in(page: Page):
    email = unique_email("unverified")
    SignupPage(page).open().fill(email=email).submit.click()
    expect(page).to_have_url(re.compile(r"/signup/check-email"))

    login = LoginPage(page).open().login(email, "Str0ng!Pass")
    expect(login.error).to_have_text("Please verify your email address before logging in.")
    expect(page.get_by_role("button", name="Resend verification email")).to_be_visible()


@pytest.mark.parametrize(
    "overrides, field, message",
    [
        ({"name": ""}, "name", "Name is required."),
        ({"name": "x" * 51}, "name", "Name must be 50 characters or fewer."),
        ({"email": ""}, "email", "Email is required."),
        ({"email": "not-an-email"}, "email", "Enter a valid email address."),
        ({"email": "user@example.com"}, "email", "An account with this email already exists."),
        ({"password": "short", "confirm": "short"}, "password", "at least 8 characters"),
        ({"password": "alllowercase1!", "confirm": "alllowercase1!"}, "password", "an uppercase letter"),
        ({"confirm": "Different1!"}, "confirm_password", "Passwords do not match."),
        ({"accept_terms": False}, "terms", "You must accept the Terms of Service."),
        ({"experience": ""}, "experience", "Please choose your experience level."),
    ],
    ids=["name-empty", "name-too-long", "email-empty", "email-invalid", "email-taken",
         "password-short", "password-no-upper", "password-mismatch", "terms-unchecked", "experience-missing"],
)
def test_signup_validation(page: Page, overrides, field, message):
    """Data-driven test: one test function, many input combinations."""
    signup = SignupPage(page).open()
    signup.fill(**{"email": unique_email(), **overrides})
    signup.submit.click()

    expect(page).to_have_url(re.compile(r"/signup$"))  # stayed on the form
    expect(signup.error_for(field)).to_contain_text(message)
    expect(page.get_by_test_id("form-error-summary")).to_be_visible()


def test_signup_keeps_entered_values_after_error(page: Page):
    signup = SignupPage(page).open()
    signup.fill(name="Sticky Name", email="sticky@example.com", accept_terms=False)
    signup.submit.click()

    expect(signup.name).to_have_value("Sticky Name")
    expect(signup.email).to_have_value("sticky@example.com")
    expect(signup.experience).to_have_value("new")
    expect(signup.password).to_have_value("")  # passwords are cleared after a failed submit


def test_invalid_field_is_marked_for_accessibility(page: Page):
    signup = SignupPage(page).open()
    signup.fill(email="bad", accept_terms=True)
    signup.submit.click()
    expect(signup.email).to_have_attribute("aria-invalid", "true")
    expect(signup.email).to_have_accessible_description("Enter a valid email address.")


@pytest.mark.parametrize(
    "password, label",
    [("", "Too short"), ("abc", "Weak"), ("abcdefgh1", "Fair"), ("Abcdefgh1", "Good"), ("Abcdefgh1!", "Strong")],
)
def test_password_strength_meter(page: Page, password, label):
    signup = SignupPage(page).open()
    signup.password.fill(password)
    expect(signup.strength_label).to_have_text(label)


def test_password_rules_checklist_updates_live(page: Page):
    signup = SignupPage(page).open()
    rule = page.locator("[data-rule=upper]")
    expect(rule).not_to_have_class(re.compile(r"\bmet\b"))
    signup.password.press_sequentially("aB")  # types key by key, like a real user
    expect(rule).to_have_class(re.compile(r"\bmet\b"))


def test_show_password_toggle(page: Page):
    signup = SignupPage(page).open()
    signup.password.fill("secret")
    expect(signup.password).to_have_attribute("type", "password")
    page.get_by_role("button", name="Show password").first.click()
    expect(signup.password).to_have_attribute("type", "text")
