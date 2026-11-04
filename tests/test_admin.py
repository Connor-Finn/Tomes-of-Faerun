"""Role-based access control. admin_page reuses a saved login (storage state)."""
import re

from playwright.sync_api import Page, expect

from pages import LoginPage


def test_regular_user_sees_access_denied(logged_in_page: Page):
    logged_in_page.goto("/admin/users")
    expect(logged_in_page.get_by_role("heading", name="Access denied")).to_be_visible()
    expect(logged_in_page.get_by_test_id("nav-admin")).to_have_count(0)
    expect(logged_in_page.get_by_test_id("user-row")).to_have_count(0)


def test_admin_api_refuses_regular_user(user_api):
    """The page hides the data, but the real protection is the API returning 403."""
    response = user_api.get("/api/admin/users")
    assert response.status == 403


def test_anonymous_user_is_sent_to_login(page: Page):
    page.goto("/admin/users")
    expect(page).to_have_url(re.compile(r"/login\?next="))


def test_admin_sees_user_list(admin_page: Page):
    admin_page.goto("/admin/users")
    expect(admin_page.get_by_role("heading", name="User management")).to_be_visible()
    expect(admin_page.locator("[data-testid=user-row][data-email='user@example.com']")).to_be_visible()


def test_admin_search_users(admin_page: Page, create_user):
    target = create_user(name="Findable Fiona the Bard")
    admin_page.goto("/admin/users")
    admin_page.get_by_label("Search users").fill("Findable")
    admin_page.get_by_role("button", name="Search").click()
    rows = admin_page.get_by_test_id("user-row")
    expect(rows).to_have_count(1)
    expect(rows).to_contain_text(target["email"])


def test_admin_bans_user_and_user_cannot_log_in(admin_page: Page, page: Page, create_user):
    """Two browsers at once: `admin_page` and `page` have separate sessions."""
    victim = create_user()

    admin_page.goto(f"/admin/users?q={victim['email']}")
    row = admin_page.get_by_test_id("user-row").filter(has_text=victim["email"])
    admin_page.once("dialog", lambda d: d.accept())
    row.get_by_role("button", name="Ban").click()
    expect(admin_page.get_by_test_id("flash-success")).to_have_text(f"{victim['email']} has been banned.")
    expect(row.get_by_test_id("user-status")).to_have_text("Banned")

    login = LoginPage(page).open().login(victim["email"], victim["password"])
    expect(login.error).to_have_text("This account has been suspended. Contact support.")


def test_admin_promotes_user(admin_page: Page, create_user):
    target = create_user()
    admin_page.goto(f"/admin/users?q={target['email']}")
    row = admin_page.get_by_test_id("user-row").filter(has_text=target["email"])
    admin_page.once("dialog", lambda d: d.accept())
    row.get_by_role("button", name="Make admin").click()
    expect(admin_page.get_by_test_id("flash-success")).to_have_text(f"{target['email']} is now an admin.")
    expect(row.get_by_role("button", name="Remove admin")).to_be_visible()


def test_dismissing_confirm_does_nothing(admin_page: Page, create_user):
    target = create_user()
    admin_page.goto(f"/admin/users?q={target['email']}")
    row = admin_page.get_by_test_id("user-row").filter(has_text=target["email"])
    admin_page.once("dialog", lambda d: d.dismiss())
    row.get_by_role("button", name="Ban").click()
    expect(row.get_by_test_id("user-status")).to_have_text("Active")


def test_admin_cannot_ban_self(admin_page: Page):
    admin_page.goto("/admin/users")
    me = admin_page.locator("[data-testid=user-row][data-email='admin@example.com']")
    expect(me.get_by_role("button")).to_have_count(0)
    expect(me).to_contain_text("(you)")
