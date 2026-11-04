from playwright.sync_api import Page


class LoginPage:
    URL = "/login"

    def __init__(self, page: Page):
        self.page = page
        # Prefer user-facing locators (label, role, text) over CSS selectors.
        self.email = page.get_by_label("Email")
        self.password = page.get_by_label("Password", exact=True)
        self.remember_me = page.get_by_label("Remember me")
        self.submit = page.get_by_role("button", name="Log in")
        self.error = page.get_by_test_id("login-error")
        self.forgot_password_link = page.get_by_role("link", name="Forgot password?")

    def open(self, next_path: str | None = None) -> "LoginPage":
        self.page.goto(self.URL if next_path is None else f"{self.URL}?next={next_path}")
        return self

    def login(self, email: str, password: str, remember: bool = False) -> "LoginPage":
        self.email.fill(email)
        self.password.fill(password)
        if remember:
            self.remember_me.check()
        # The page is a React app, so a failed login doesn't reload anything. Waiting for
        # the API response makes sure each attempt has finished before the test moves on.
        with self.page.expect_response("**/api/auth/login"):
            self.submit.click()
        return self
