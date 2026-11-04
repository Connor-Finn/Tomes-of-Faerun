"""Page Object Model: one class per page, wrapping its locators and actions.

Tests then read like user stories ("login_page.login(...)") and when the UI
changes you fix ONE class instead of fifty tests.
"""
from .login_page import LoginPage
from .signup_page import SignupPage
from .tavern_page import TavernPage, TomePage

__all__ = ["LoginPage", "SignupPage", "TavernPage", "TomePage"]
