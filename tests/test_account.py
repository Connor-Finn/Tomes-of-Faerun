"""Account management: profile, avatar upload, change password, delete account."""
import base64
import re

from playwright.sync_api import Page, expect

from pages import LoginPage

# A real 1x1 PNG, built in memory so the test needs no fixture files on disk.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_update_profile(logged_in_page: Page):
    page = logged_in_page
    page.goto("/account/profile")

    page.get_by_label("Display name").fill("Renamed Person")
    page.get_by_label("Bio").fill("I play a halfling rogue.")
    page.get_by_label("Time zone").select_option("Europe/London")
    page.get_by_label("Seasoned veteran").check()            # radio button
    page.get_by_label("Party message notifications").check()  # checkbox
    page.get_by_label("Email notifications").uncheck()
    page.get_by_role("button", name="Save changes").click()

    expect(page.get_by_test_id("flash-success")).to_have_text("Profile updated successfully.")

    # Reload to prove the changes were saved on the server, not just in the browser.
    page.reload()
    expect(page.get_by_label("Display name")).to_have_value("Renamed Person")
    expect(page.get_by_label("Bio")).to_have_value("I play a halfling rogue.")
    expect(page.get_by_label("Time zone")).to_have_value("Europe/London")
    expect(page.get_by_label("Seasoned veteran")).to_be_checked()
    expect(page.get_by_label("Party message notifications")).to_be_checked()
    expect(page.get_by_label("Email notifications")).not_to_be_checked()
    expect(page.get_by_test_id("user-menu-button")).to_contain_text("Renamed Person")


def test_profile_requires_name(logged_in_page: Page):
    page = logged_in_page
    page.goto("/account/profile")
    page.get_by_label("Display name").fill("")
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_test_id("error-name")).to_have_text("Name is required.")


def test_email_field_is_read_only(logged_in_page: Page, user):
    page = logged_in_page
    page.goto("/account/profile")
    email = page.get_by_label("Email", exact=True)
    expect(email).to_be_disabled()
    expect(email).to_have_value(user["email"])


def test_bio_character_counter(logged_in_page: Page):
    page = logged_in_page
    page.goto("/account/profile")
    page.get_by_label("Bio").fill("Hello")
    expect(page.get_by_test_id("bio-counter")).to_have_text("5 / 200")


def test_upload_avatar(logged_in_page: Page):
    page = logged_in_page
    page.goto("/account/profile")
    expect(page.get_by_test_id("avatar-placeholder")).to_be_visible()

    page.get_by_label("Upload a new avatar").set_input_files(
        {"name": "me.png", "mimeType": "image/png", "buffer": TINY_PNG}
    )
    page.get_by_role("button", name="Upload avatar").click()

    expect(page.get_by_test_id("flash-success")).to_have_text("Avatar updated.")
    avatar = page.get_by_test_id("avatar-image")
    expect(avatar).to_have_attribute("src", re.compile(r"/uploads/user\d+_\w+\.png"))
    # Check the browser actually loaded the image (naturalWidth stays 0 for broken images).
    page.wait_for_function("img => img.complete && img.naturalWidth === 1", arg=avatar.element_handle())


def test_avatar_rejects_non_image(logged_in_page: Page):
    page = logged_in_page
    page.goto("/account/profile")
    page.get_by_label("Upload a new avatar").set_input_files(
        {"name": "virus.exe", "mimeType": "application/octet-stream", "buffer": b"MZ..."}
    )
    page.get_by_role("button", name="Upload avatar").click()
    expect(page.get_by_test_id("flash-error")).to_have_text("Avatar must be a PNG, JPG or GIF image.")


def test_change_password(logged_in_page: Page, user):
    page = logged_in_page
    page.goto("/account/security")
    page.get_by_label("Current password").fill(user["password"])
    page.get_by_label("New password", exact=True).fill("Changed456!")
    page.get_by_label("Confirm new password").fill("Changed456!")
    page.get_by_role("button", name="Update password").click()
    expect(page.get_by_test_id("flash-success")).to_have_text("Password changed successfully.")

    # Log out and back in with the new password.
    page.context.clear_cookies()
    login = LoginPage(page).open().login(user["email"], user["password"])
    expect(login.error).to_have_text("Invalid email or password.")
    login.login(user["email"], "Changed456!")
    expect(page).to_have_url(re.compile(r"/guild-hall$"))


def test_change_password_wrong_current(logged_in_page: Page):
    page = logged_in_page
    page.goto("/account/security")
    page.get_by_label("Current password").fill("NotMyPassword1!")
    page.get_by_label("New password", exact=True).fill("Changed456!")
    page.get_by_label("Confirm new password").fill("Changed456!")
    page.get_by_role("button", name="Update password").click()
    expect(page.get_by_test_id("error-current_password")).to_have_text("Current password is incorrect.")


def test_delete_account(logged_in_page: Page, user):
    page = logged_in_page
    page.goto("/account/security")
    page.get_by_role("button", name="Delete my account").click()

    dialog = page.get_by_role("dialog", name="Delete account?")
    expect(dialog).to_be_visible()
    confirm = dialog.get_by_role("button", name="Permanently delete account")
    expect(confirm).to_be_disabled()

    dialog.get_by_label("Your password").fill(user["password"])
    dialog.get_by_label("Type DELETE to confirm").fill("DELETE")
    expect(confirm).to_be_enabled()
    confirm.click()

    expect(page.get_by_test_id("flash-info")).to_have_text("Your account has been permanently deleted.")
    login = LoginPage(page).open().login(user["email"], user["password"])
    expect(login.error).to_have_text("Invalid email or password.")


def test_cancel_delete_keeps_account(logged_in_page: Page):
    page = logged_in_page
    page.goto("/account/security")
    page.get_by_role("button", name="Delete my account").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("button", name="Cancel").click()
    expect(dialog).to_be_hidden()
    page.goto("/guild-hall")
    expect(page).to_have_url(re.compile(r"/guild-hall$"))
