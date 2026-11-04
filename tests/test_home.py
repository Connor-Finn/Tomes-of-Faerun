"""Landing page, navigation and the 404 page."""
import re

from playwright.sync_api import Page, expect


def test_home_page_introduces_the_app(page: Page):
    page.goto("/")
    expect(page).to_have_title("Tomes of Faerun")
    expect(page.get_by_role("heading", level=1)).to_have_text("Your adventures, bound in one tome.")
    expect(page.get_by_test_id("feature-card")).to_have_count(7)
    expect(page.get_by_test_id("feature-card").filter(has_text="Bestiary")).to_be_visible()


def test_call_to_action_opens_signup(page: Page):
    page.goto("/")
    page.get_by_role("link", name="Start your adventure").click()
    expect(page).to_have_url(re.compile(r"/signup$"))
    expect(page.get_by_role("heading", name="Create your account")).to_be_visible()


def test_logged_in_home_links_to_tavern(logged_in_page: Page, user):
    logged_in_page.get_by_test_id("nav-home").click()
    logged_in_page.get_by_role("link", name="Enter the tavern").click()
    expect(logged_in_page.get_by_role("heading", name="The Tavern", level=1)).to_be_visible()
    expect(logged_in_page.get_by_text(f"Pull up a chair, {user['name']}")).to_be_visible()


def test_unknown_page_shows_not_found(page: Page):
    page.goto("/no/such/page")
    expect(page.get_by_role("heading", name="Page not found")).to_be_visible()


def test_mobile_layout_has_no_horizontal_scroll(browser, browser_context_args):
    context = browser.new_context(**{**browser_context_args, "viewport": {"width": 375, "height": 740}})
    page = context.new_page()
    page.goto("/")
    expect(page.get_by_test_id("feature-card").first).to_be_visible()
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 0
    context.close()
