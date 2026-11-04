"""The guild hall hub, Player / Dungeon Master modes, and the tome layout every section uses."""
import re

import pytest
from playwright.sync_api import Page, expect

from pages import LoginPage, GuildHallPage, TomePage

PLAYER_TOMES = ["Campaigns", "Character Manager", "Solo Adventure"]
DM_TOMES = ["Campaigns", "Browse Tomes", "Create Solo Adventure", "Create Homebrew"]

# (path, tome title, first chapter) for every section that has pages.
OPEN_SECTIONS = [
    ("/play/campaigns", "Campaigns", "Current campaigns"),
    ("/play/characters", "Character Manager", "My characters"),
    ("/dm/campaigns", "Campaigns", "Your campaigns"),
    ("/dm/tomes", "Browse Tomes", "Spells"),
]
SEALED_SECTIONS = ["/play/solo-adventure", "/dm/solo-adventures", "/dm/homebrew"]


# ---------------------------------------------------------------------------
# The hub
# ---------------------------------------------------------------------------
def test_login_lands_in_the_guild_hall_in_player_mode(logged_in_page: Page, user):
    hall = GuildHallPage(logged_in_page)
    expect(hall.heading).to_be_visible()
    expect(logged_in_page.get_by_text(f"Pull up a chair, {user['name']}")).to_be_visible()
    expect(hall.player_mode).to_be_checked()
    expect(hall.shelf_heading).to_have_text("The adventurer's shelf")
    expect(hall.covers.locator(".book-title")).to_have_text(PLAYER_TOMES)


def test_switching_to_dungeon_master_mode_changes_the_shelf(logged_in_page: Page):
    hall = GuildHallPage(logged_in_page).switch_to("dm")
    expect(hall.dm_mode).to_be_checked()
    expect(hall.shelf_heading).to_have_text("The Dungeon Master's shelf")
    expect(hall.covers.locator(".book-title")).to_have_text(DM_TOMES)

    hall.switch_to("player")
    expect(hall.covers.locator(".book-title")).to_have_text(PLAYER_TOMES)


def test_mode_is_remembered_after_a_reload(logged_in_page: Page):
    hall = GuildHallPage(logged_in_page).switch_to("dm")
    logged_in_page.reload()
    expect(hall.dm_mode).to_be_checked()
    expect(hall.tome("Browse Tomes")).to_be_visible()


def test_mode_switch_works_from_the_keyboard(logged_in_page: Page):
    hall = GuildHallPage(logged_in_page)
    hall.player_mode.focus()
    logged_in_page.keyboard.press("ArrowRight")
    expect(hall.dm_mode).to_be_checked()
    expect(hall.tome("Create Homebrew")).to_be_visible()


def test_sealed_tomes_are_marked_on_the_shelf(logged_in_page: Page):
    hall = GuildHallPage(logged_in_page)
    expect(hall.tome("Solo Adventure")).to_contain_text("Sealed")
    expect(hall.tome("Character Manager")).not_to_contain_text("Sealed")


def test_guild_hall_needs_an_account(page: Page):
    page.goto("/guild-hall")
    expect(page).to_have_url(re.compile(r"/login\?next=%2Fguild-hall$"))


def test_old_dashboard_link_goes_to_the_guild_hall(logged_in_page: Page):
    logged_in_page.goto("/dashboard")
    expect(logged_in_page).to_have_url(re.compile(r"/guild-hall$"))


def test_topbar_links_back_to_the_guild_hall(logged_in_page: Page):
    logged_in_page.goto("/account/profile")
    logged_in_page.get_by_test_id("nav-guild-hall").click()
    expect(GuildHallPage(logged_in_page).heading).to_be_visible()


# ---------------------------------------------------------------------------
# Tomes
# ---------------------------------------------------------------------------
def test_opening_a_tome_shows_its_contents_and_first_page(logged_in_page: Page):
    tome = GuildHallPage(logged_in_page).open_tome("Character Manager")
    expect(logged_in_page).to_have_url(re.compile(r"/play/characters/my-characters$"))
    expect(tome.title).to_have_text("Character Manager")
    expect(tome.entries).to_have_text(["My characters", "Create a character", "Publish a character"])
    expect(tome.current_entry).to_have_text("My characters")
    expect(tome.page_title).to_have_text("My characters")
    expect(tome.folio).to_have_text("Page 1 of 3")


def test_contents_jump_to_a_chapter(logged_in_page: Page):
    tome = TomePage(logged_in_page).open("/play/characters").go_to("Publish a character")
    expect(logged_in_page).to_have_url(re.compile(r"/play/characters/publish$"))
    expect(tome.page_title).to_have_text("Publish a character")
    expect(tome.current_entry).to_have_text("Publish a character")
    expect(tome.folio).to_have_text("Page 3 of 3")
    expect(tome.next_page).to_have_count(0)  # last page: nothing to turn to


def test_turning_pages_forwards_and_back(logged_in_page: Page):
    tome = TomePage(logged_in_page).open("/dm/tomes")
    expect(tome.prev_page).to_have_count(0)  # first page
    tome.next_page.click()
    expect(tome.page_title).to_have_text("Bestiary")
    tome.next_page.click()
    expect(tome.page_title).to_have_text("Monster collections")
    tome.prev_page.click()
    expect(tome.page_title).to_have_text("Bestiary")
    expect(tome.folio).to_have_text("Page 2 of 5")

    logged_in_page.go_back()  # browser history follows the pages
    expect(tome.page_title).to_have_text("Monster collections")


def test_unbuilt_pages_show_what_is_planned(logged_in_page: Page):
    TomePage(logged_in_page).open("/dm/campaigns/requests")
    draft = logged_in_page.get_by_test_id("draft-page")
    expect(draft.get_by_text("Being written")).to_be_visible()
    expect(draft.get_by_role("listitem").filter(has_text="ask to join")).to_be_visible()


@pytest.mark.parametrize("path,title,first_chapter", OPEN_SECTIONS)
def test_every_section_opens_on_its_first_chapter(logged_in_page: Page, path, title, first_chapter):
    tome = TomePage(logged_in_page).open(path)
    expect(tome.title).to_have_text(title)
    expect(tome.page_title).to_have_text(first_chapter)
    expect(tome.current_entry).to_have_text(first_chapter)


@pytest.mark.parametrize("path", SEALED_SECTIONS)
def test_sealed_sections_say_they_are_not_written_yet(logged_in_page: Page, path):
    tome = TomePage(logged_in_page).open(path)
    expect(tome.page_title).to_have_text("This tome is still sealed")
    expect(tome.contents).to_have_count(0)


def test_deep_link_switches_to_that_sections_mode(logged_in_page: Page):
    tome = TomePage(logged_in_page).open("/dm/campaigns/requests")
    expect(tome.breadcrumbs).to_contain_text("Dungeon Master Mode")
    tome.breadcrumbs.get_by_role("link", name="Guild Hall").click()
    hall = GuildHallPage(logged_in_page)
    expect(hall.dm_mode).to_be_checked()


def test_unknown_page_in_a_tome(logged_in_page: Page):
    tome = TomePage(logged_in_page).open("/play/campaigns/no-such-page")
    expect(tome.page_title).to_have_text("This page is missing")
    expect(tome.current_entry).to_have_count(0)
    logged_in_page.get_by_role("link", name="Go to the first page").click()
    expect(tome.page_title).to_have_text("Current campaigns")


def test_tomes_need_an_account(page: Page):
    page.goto("/play/characters/create")
    expect(page).to_have_url(re.compile(r"/login\?next=%2Fplay%2Fcharacters%2Fcreate$"))


@pytest.mark.parametrize("path", ["/guild-hall", "/play/characters/create"])
def test_mobile_layout_has_no_horizontal_scroll(browser, browser_context_args, user, path):
    context = browser.new_context(**{**browser_context_args, "viewport": {"width": 375, "height": 740}})
    page = context.new_page()
    LoginPage(page).open(next_path=path).login(user["email"], user["password"])
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 0
    context.close()
