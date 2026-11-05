"""Level roadmaps in the browser: plan them in the Character Manager, follow them in a campaign,
keep a backup copy, and share them when publishing.

Data the test isn't about (characters, parties, planned levels) is set up through the API with the
browser's own session, so each test only clicks through the part it's checking.
"""
from __future__ import annotations

import re
import uuid

import pytest
from playwright.sync_api import Browser, Page, expect

from builds import aldric, autofill, level_up
from conftest import API_HEADERS
from pages import (BuilderPage, CampaignCharacterPage, CharacterPage, InstanceRoadmapPanel, LevelUpPage, LoginPage, RoadmapPage,
                   RoadmapsPage)
from pages.sharing_pages import PublishedCharactersPage, PublishPage


# ------------------------------------------------------------------ helpers
def post(page: Page, url: str, data: dict | None = None, method: str = "post") -> dict:
    response = getattr(page.request, method)(url, data=data or {}, headers=API_HEADERS)
    assert response.ok, response.text()
    return response.json()


def give_character(page: Page, name: str = "Aldric Vane") -> dict:
    return post(page, "/api/characters", {"build": {**aldric(), "name": name}})["character"]


def give_roadmap(page: Page, character_id: int, name: str = "Champion route", to_level: int = 1) -> dict:
    """A roadmap planned up to `to_level`, made the way the builder would (fighters' SRD subclass is Champion)."""
    roadmap = post(page, f"/api/characters/{character_id}/roadmaps", {"name": name})["roadmap"]
    check = lambda b: post(page, "/api/characters/check", {"build": b})  # noqa: E731
    for level in range(2, to_level + 1):
        build = post(page, f"/api/roadmaps/{roadmap['id']}/levels/{level}", method="get")["character"]["build"]
        if level >= 3:
            build["subclass"] = "champion"
        roadmap = post(page, f"/api/roadmaps/{roadmap['id']}/levels/{level}", {"build": autofill(check, build)},
                       method="put")["roadmap"]
    return roadmap


@pytest.fixture
def player(create_user) -> dict:
    return create_user(name="Mira Thorn")


@pytest.fixture
def player_page(browser: Browser, browser_context_args: dict, player: dict) -> Page:
    """A second browser, logged in as the player. `logged_in_page` is the Dungeon Master."""
    context = browser.new_context(**browser_context_args)
    page = context.new_page()
    LoginPage(page).open().login(player["email"], player["password"])
    expect(page).to_have_url(re.compile(r"/guild-hall$"))
    yield page
    context.close()


@pytest.fixture
def table(logged_in_page: Page, player_page: Page, player: dict) -> dict:
    """A campaign whose party has the player in it."""
    party = post(logged_in_page, "/api/parties", {"name": "The Lantern Bearers"})["party"]
    post(logged_in_page, f"/api/parties/{party['id']}/invites", {"email": player["email"]})
    post(player_page, f"/api/parties/{party['id']}/accept")
    campaign = post(logged_in_page, "/api/campaigns", {"name": "The Whispering Dead", "status": "active"})["campaign"]
    post(logged_in_page, f"/api/campaigns/{campaign['id']}", {"party_id": party["id"]}, method="patch")
    return {"id": campaign["id"]}


def join(page: Page, table: dict, character: dict) -> None:
    post(page, f"/api/campaigns/{table['id']}/instance", {"character_id": character["id"]})


# ------------------------------------------------------------------ planning
def test_plan_a_roadmap_level_by_level(logged_in_page: Page):
    character = give_character(logged_in_page)
    roadmaps = RoadmapsPage(logged_in_page).open(character["id"])
    expect(roadmaps.empty).to_be_visible()
    roadmap = roadmaps.start("Champion route")

    expect(logged_in_page).to_have_url(re.compile(rf"/play/characters/c/{character['id']}/roadmaps/\d+$"))
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Roadmap “Champion route” started at level 1.")
    expect(roadmap.page_title).to_have_text("Champion route")
    expect(roadmap.level(1)).to_contain_text("Where it starts")

    # Level 2: fighters gain Action Surge, with nothing to choose
    roadmap.plan_next.click()
    builder = BuilderPage(logged_in_page)
    expect(builder.heading).to_have_text("Planning level 2 for Aldric Vane")
    expect(logged_in_page.get_by_test_id("roadmap-builder-note")).to_contain_text("stays at level 1")
    expect(builder.tab("Race")).to_have_count(0)   # a roadmap never changes who the character is
    expect(builder.status).to_have_text("Complete: ready to play.")
    builder.save()
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Level 2 is planned in “Champion route”.")
    expect(roadmap.level(2)).to_contain_text("Action Surge")

    # Level 3: the subclass
    roadmap.plan_next.click()
    expect(builder.heading).to_have_text("Planning level 3 for Aldric Vane")
    builder.go_to("Class")
    builder.choose_card("champion")
    builder.save()
    expect(roadmap.level(3)).to_contain_text("Subclass: Champion")
    expect(roadmap.level(3)).to_contain_text("Improved Critical")
    expect(roadmap.plan_next).to_have_text("Plan level 4")

    # The character itself is still level 1
    sheet = CharacterPage(logged_in_page).open_character(character["id"])
    expect(logged_in_page.locator(".tome-subtitle")).to_contain_text("Level 1 Human Fighter")
    sheet.go_to("Roadmaps")
    expect(RoadmapsPage(logged_in_page).card("Champion route")).to_contain_text("Levels 1 to 3")


def test_an_unfinished_level_isnt_saved(logged_in_page: Page):
    character = give_character(logged_in_page)
    roadmap = give_roadmap(logged_in_page, character["id"], to_level=2)
    logged_in_page.goto(f"/play/characters/c/{character['id']}/roadmaps/{roadmap['id']}/level/3")
    builder = BuilderPage(logged_in_page)
    builder.save()   # no subclass chosen
    expect(builder.errors).to_contain_text("Choose a subclass.")


def test_replanning_an_earlier_level_asks_first(logged_in_page: Page):
    character = give_character(logged_in_page)
    made = give_roadmap(logged_in_page, character["id"], to_level=4)
    roadmap = RoadmapPage(logged_in_page).open(character["id"], made["id"])
    roadmap.level(2).get_by_role("link", name="Re-plan from here").click()

    builder = BuilderPage(logged_in_page)
    expect(builder.heading).to_have_text("Planning level 2 for Aldric Vane")
    builder.save()
    dialog = logged_in_page.get_by_role("dialog")
    expect(dialog).to_contain_text("The roadmap has 2 levels planned after level 2.")
    dialog.get_by_role("button", name="Save and clear 2 later levels").click()

    expect(logged_in_page.get_by_test_id("flash-success").last).to_contain_text("The 2 levels planned after it were cleared.")
    expect(roadmap.levels).to_have_count(2)
    expect(roadmap.plan_next).to_have_text("Plan level 3")


def test_remove_levels_rename_and_delete(logged_in_page: Page):
    character = give_character(logged_in_page)
    made = give_roadmap(logged_in_page, character["id"], to_level=3)
    roadmap = RoadmapPage(logged_in_page).open(character["id"], made["id"])

    roadmap.level(2).get_by_role("button", name="Remove this level and up").click()
    expect(roadmap.dialog).to_contain_text("The roadmap will end at level 1.")
    roadmap.dialog.get_by_role("button", name="Remove").click()
    expect(roadmap.levels).to_have_count(1)

    roadmap.name.fill("Sword and board")
    roadmap.rename_button.click()
    expect(roadmap.page_title).to_have_text("Sword and board")

    roadmap.delete_button.click()
    roadmap.dialog.get_by_role("button", name="Delete roadmap").click()
    expect(logged_in_page).to_have_url(re.compile(rf"/play/characters/c/{character['id']}/roadmaps$"))
    expect(RoadmapsPage(logged_in_page).empty).to_be_visible()


def test_drafts_cant_start_a_roadmap(logged_in_page: Page):
    draft = post(logged_in_page, "/api/characters", {"build": {"name": "Half Done", "level": 1, "choices": {}}})["character"]
    roadmaps = RoadmapsPage(logged_in_page).open(draft["id"])
    expect(roadmaps.unavailable).to_have_text("Finish Half Done in the builder before planning level-ups.")
    expect(roadmaps.start_button).to_have_count(0)


# ------------------------------------------------------------------ following in a campaign
def test_follow_a_roadmap_and_level_up_along_it(table: dict, player_page: Page):
    character = give_character(player_page)
    give_roadmap(player_page, character["id"], to_level=3)
    join(player_page, table, character)
    CampaignCharacterPage(player_page).open_player(table["id"], "character")
    panel = InstanceRoadmapPanel(player_page)

    panel.follow("Champion route")
    expect(player_page.get_by_test_id("flash-success").last).to_have_text(
        "Aldric Vane now follows “Champion route”. Your previous choices were saved as the backup.")
    expect(panel.following).to_have_text("Following Champion route (levels 1 to 3).")
    expect(panel.backup_summary).to_contain_text("Level 1 Human Fighter")
    expect(panel.backup_summary).to_contain_text("Before following “Champion route”")

    for level in (2, 3):
        panel.level_up.click()
        levelling = LevelUpPage(player_page)
        expect(levelling.roadmap_note).to_contain_text("Following “Champion route”")
        levelling.choose_hp("average")
        levelling.confirm()
        expect(player_page.get_by_test_id("flash-success").last).to_contain_text(f"is now level {level}")
    expect(player_page.locator(".page-summary").first).to_contain_text("Level 3 Human Fighter (Champion)")
    expect(panel.ends).to_contain_text("The roadmap ends at level 3.")

    # The roadmap shows who follows it
    player_page.goto(f"/play/characters/c/{character['id']}/roadmaps")
    expect(RoadmapsPage(player_page).card("Champion route")).to_contain_text("followed in The Whispering Dead")


def test_a_roadmap_that_hasnt_reached_the_level_cant_be_chosen(table: dict, player_page: Page):
    character = give_character(player_page)
    give_roadmap(player_page, character["id"], "Too short", to_level=1)
    join(player_page, table, character)
    level_up(player_page.request, f"/api/campaigns/{table['id']}", 2, headers=API_HEADERS)

    CampaignCharacterPage(player_page).open_player(table["id"], "character")
    panel = InstanceRoadmapPanel(player_page)
    expect(panel.roadmap_select.locator("option", has_text="Too short")).to_have_js_property("disabled", True)
    expect(panel.roadmap).to_contain_text("Roadmaps that don't plan level 2 yet can't be followed")


def test_level_up_fills_in_the_roadmaps_picks(table: dict, player_page: Page):
    character = give_character(player_page)
    roadmap = give_roadmap(player_page, character["id"], to_level=3)
    join(player_page, table, character)
    post(player_page, f"/api/campaigns/{table['id']}/instance/roadmap", {"roadmap_id": roadmap["id"]}, method="put")
    level_up(player_page.request, f"/api/campaigns/{table['id']}", 2, headers=API_HEADERS)

    levelling = LevelUpPage(player_page).open(table["id"])
    expect(levelling.roadmap_note).to_contain_text("Changing them stops following the roadmap.")
    expect(levelling.subclass.get_by_role("radio", name=re.compile("^Champion"))).to_be_checked()
    levelling.choose_hp("average")
    levelling.confirm()
    expect(player_page.get_by_test_id("flash-success").last).to_contain_text("Following “Champion route”.")
    expect(InstanceRoadmapPanel(player_page).following).to_contain_text("Following Champion route")


def test_no_roadmaps_points_to_the_character_manager(table: dict, player_page: Page):
    character = give_character(player_page)
    join(player_page, table, character)
    CampaignCharacterPage(player_page).open_player(table["id"], "character")
    note = player_page.get_by_test_id("no-instance-roadmaps")
    expect(note).to_contain_text("Aldric Vane has no roadmaps yet.")
    note.get_by_role("link", name="Plan one in the Character Manager").click()
    expect(player_page).to_have_url(re.compile(rf"/play/characters/c/{character['id']}/roadmaps$"))


# ------------------------------------------------------------------ backups
def test_save_restore_and_delete_a_backup(table: dict, player_page: Page):
    character = give_character(player_page)
    join(player_page, table, character)
    CampaignCharacterPage(player_page).open_player(table["id"], "character")
    panel = InstanceRoadmapPanel(player_page)

    panel.save_backup.click()
    expect(panel.backup_summary).to_contain_text("Level 1 Human Fighter")
    expect(panel.backup_summary).to_contain_text("Saved by hand")

    # Level up by hand, then go back to the backup: the two swap places
    level_up(player_page.request, f"/api/campaigns/{table['id']}", 2, headers=API_HEADERS)
    player_page.reload()
    expect(player_page.locator(".page-summary").first).to_contain_text("Level 2")

    panel.restore.click()
    expect(panel.dialog).to_contain_text("nothing is lost")
    panel.dialog.get_by_role("button", name="Swap them").click()
    expect(player_page.locator(".page-summary").first).to_contain_text("Level 1 Human Fighter")
    expect(panel.backup_summary).to_contain_text("Level 2 Human Fighter")

    panel.back_up_again.click()
    expect(panel.dialog).to_contain_text("Each campaign keeps one backup.")
    panel.dialog.get_by_role("button", name="Replace the backup").click()
    expect(panel.backup_summary).to_contain_text("Level 1 Human Fighter")

    panel.delete_backup.click()
    panel.dialog.get_by_role("button", name="Delete the backup").click()
    expect(panel.save_backup).to_be_visible()


def test_switching_with_a_backup_already_saved_warns_it_is_replaced(table: dict, player_page: Page):
    character = give_character(player_page)
    give_roadmap(player_page, character["id"])
    join(player_page, table, character)
    post(player_page, f"/api/campaigns/{table['id']}/instance/backup", method="put")
    CampaignCharacterPage(player_page).open_player(table["id"], "character")
    panel = InstanceRoadmapPanel(player_page)
    panel.roadmap_select.select_option(index=1)
    panel.follow_button.click()
    expect(player_page.get_by_test_id("replaces-backup")).to_contain_text("This replaces the backup saved on")
    panel.keep_backup.uncheck()
    expect(player_page.get_by_test_id("replaces-backup")).to_have_count(0)


# ------------------------------------------------------------------ publishing
def test_publish_with_a_roadmap_and_the_copy_gets_it(logged_in_page: Page, browser: Browser,
                                                     browser_context_args: dict, create_user):
    hero = f"Sir Corwin {uuid.uuid4().hex[:6]}"
    character = give_character(logged_in_page, hero)
    give_roadmap(logged_in_page, character["id"], "Champion route", to_level=3)
    give_roadmap(logged_in_page, character["id"], "Secret plan")

    author = PublishPage(logged_in_page).open()
    author.character.select_option(label=f"{hero}: Level 1 Human Fighter")
    roadmaps = logged_in_page.get_by_test_id("publish-roadmaps")
    expect(roadmaps).to_contain_text("Include none, some or all.")
    roadmaps.get_by_role("checkbox", name=re.compile("^Champion route")).check()
    author.publish_button.click()
    expect(author.dialog.get_by_test_id("publish-roadmaps-summary")).to_have_text("Included roadmap: Champion route.")
    author.dialog.get_by_role("button", name="Publish", exact=True).click()
    expect(author.published(hero).get_by_test_id("published-roadmaps")).to_have_text(
        "Roadmaps: Champion route (levels 1 to 3)")

    # Another player copies it, and gets the roadmap too
    reader = create_user(name="Bryn Ashdown")
    context = browser.new_context(**browser_context_args)
    page = context.new_page()
    LoginPage(page).open().login(reader["email"], reader["password"])
    expect(page).to_have_url(re.compile(r"/guild-hall$"))
    browse = PublishedCharactersPage(page).open()
    browse.search.fill(hero)
    expect(browse.card(hero).get_by_test_id("published-roadmaps")).to_have_text(
        "Comes with roadmaps: Champion route (levels 1 to 3)")
    browse.use(hero)
    expect(page).to_have_url(re.compile(r"/play/characters/c/\d+/sheet$"))
    CharacterPage(page).go_to("Roadmaps")
    expect(RoadmapsPage(page).cards).to_have_count(1)
    expect(RoadmapsPage(page).card("Champion route")).to_contain_text("Levels 1 to 3")
    context.close()
