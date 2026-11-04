from playwright.sync_api import Locator, Page


class SignupPage:
    URL = "/signup"

    def __init__(self, page: Page):
        self.page = page
        self.name = page.get_by_label("Display name")
        self.email = page.get_by_label("Email")
        self.password = page.get_by_label("Password", exact=True)
        self.confirm_password = page.get_by_label("Confirm password")
        self.experience = page.get_by_label("Experience level")
        self.newsletter = page.get_by_label("Send me news about new features")
        self.terms = page.get_by_label("I agree to the Terms of Service")
        self.submit = page.get_by_role("button", name="Create account")
        self.strength_label = page.get_by_test_id("strength-label")

    def open(self) -> "SignupPage":
        self.page.goto(self.URL)
        return self

    def fill(self, name="Jane Tester", email="jane@example.com", password="Str0ng!Pass",
             confirm=None, experience="new", accept_terms=True) -> "SignupPage":
        self.name.fill(name)
        self.email.fill(email)
        self.password.fill(password)
        self.confirm_password.fill(password if confirm is None else confirm)
        if experience:
            self.experience.select_option(experience)
        if accept_terms:
            self.terms.check()
        return self

    def error_for(self, field: str) -> Locator:
        """Validation message under a field, e.g. error_for("email")."""
        return self.page.get_by_test_id(f"error-{field}")
