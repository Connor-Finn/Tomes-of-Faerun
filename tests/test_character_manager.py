"""Character Manager in the browser: My characters, templates and the character tome."""
import re

import pytest
from playwright.sync_api import Page, expect

from builds import autofill, blank
from conftest import API_HEADERS
from pages import CharacterPage, CreateCharacterPage, LoginPage, MyCharactersPage


def create_via_api(page: Page, **body) -> dict:
    """Create a character with the browser's own session (fast setup, no clicking)."""
    response = page.request.post("/api/characters", data=body, headers=API_HEADERS)
    assert response.status == 201, response.text()
    return response.json()["character"]


def check_via_api(page: Page):
    def _check(build: dict) -> dict:
        return page.request.post("/api/characters/check", data={"build": build}, headers=API_HEADERS).json()
    return _check


# ------------------------------------------------------------------ My characters
def test_a_new_player_has_no_characters_yet(logged_in_page: Page):
    my = MyCharactersPage(logged_in_page).open()
    expect(my.page_title).to_have_text("My characters")
    expect(my.empty).to_contain_text("No characters yet")
    my.empty.get_by_role("link", name="Write your first character").click()
    expect(logged_in_page).to_have_url(re.compile(r"/play/characters/create$"))


def test_start_from_a_template(logged_in_page: Page):
    create = CreateCharacterPage(logged_in_page).open()
    expect(create.templates.filter(has_text="Aldric Vane")).to_contain_text("Level 1 Human Fighter")
    character = create.use_template("Aldric Vane")

    expect(logged_in_page).to_have_url(re.compile(r"/play/characters/c/\d+/sheet$"))
    expect(logged_in_page.get_by_test_id("flash-success")).to_have_text("Aldric Vane joined your characters.")
    expect(character.title).to_have_text("Aldric Vane")
    expect(character.current_entry).to_have_text("Character sheet")
    expect(character.draft_notice).to_have_count(0)
    expect(character.stat("ac")).to_have_text("18")
    expect(character.stat("hp")).to_have_text("12")
    expect(character.stat("passive-perception")).to_have_text("13")
    expect(character.ability("str")).to_contain_text("+3")
    expect(character.ability("str")).to_contain_text("16")
    expect(logged_in_page.get_by_test_id("skill-athletics")).to_contain_text("+5")
    expect(logged_in_page.get_by_test_id("languages")).to_have_text("Celestial, Common, Dwarvish, Elvish")
    expect(logged_in_page.get_by_test_id("attacks")).to_contain_text("1d8 + 5 slashing")

    character.breadcrumbs.get_by_role("link", name="Character Manager").click()
    my = MyCharactersPage(logged_in_page)
    card = my.card("Aldric Vane")
    expect(card).to_contain_text("Level 1 Human Fighter")
    expect(card.get_by_test_id("character-status")).to_have_text("Complete")
    expect(card.get_by_test_id("character-mode")).to_have_text("Easy build")


def test_each_template_copy_is_a_separate_character(logged_in_page: Page):
    create_via_api(logged_in_page, template="human-fighter")
    create_via_api(logged_in_page, template="human-fighter")
    my = MyCharactersPage(logged_in_page).open()
    expect(my.cards).to_have_count(2)


def test_character_tome_has_a_page_for_everything(logged_in_page: Page):
    character = create_via_api(logged_in_page, template="human-fighter")
    tome = CharacterPage(logged_in_page).open_character(character["id"])
    expect(tome.entries).to_have_text(
        ["Character sheet", "Spellbook", "Inventory", "Features", "Notes", "Campaigns", "Roadmaps"])
    expect(tome.folio).to_have_text("Page 1 of 7")
    expect(tome.breadcrumbs).to_contain_text("Aldric Vane")


def test_draft_characters_say_what_is_missing(logged_in_page: Page):
    character = create_via_api(logged_in_page, build={"name": "Half-written", "race": "elf", "subrace": "high-elf"})
    tome = CharacterPage(logged_in_page).open_character(character["id"])
    expect(tome.draft_notice).to_contain_text("This character isn't finished")
    expect(tome.draft_notice).to_contain_text("Choose a class.")
    MyCharactersPage(logged_in_page).open()
    expect(MyCharactersPage(logged_in_page).card("Half-written").get_by_test_id("character-status")).to_have_text("Draft")


# ------------------------------------------------------------------ pages of the tome
def test_inventory_lists_starting_equipment(logged_in_page: Page):
    character = create_via_api(logged_in_page, template="human-fighter")
    CharacterPage(logged_in_page).open_character(character["id"], "inventory")
    expect(logged_in_page.get_by_test_id("gold")).to_have_text("15 gp")
    chain_mail = logged_in_page.get_by_test_id("inventory-item").filter(has_text="Chain Mail")
    expect(chain_mail).to_contain_text("Equipped")
    bolts = logged_in_page.get_by_test_id("inventory-item").filter(has_text="Crossbow bolt")
    expect(bolts).to_contain_text("20")


def test_features_are_grouped_by_where_they_come_from(logged_in_page: Page):
    character = create_via_api(logged_in_page, template="human-fighter")
    CharacterPage(logged_in_page).open_character(character["id"], "features")
    features = logged_in_page.get_by_test_id("features")
    expect(features.get_by_role("heading", name="Class features")).to_be_visible()
    second_wind = logged_in_page.get_by_test_id("feature").filter(has_text="Second Wind")
    second_wind.locator("summary").click()
    expect(second_wind).to_contain_text("bonus action")
    expect(logged_in_page.get_by_test_id("feature").filter(has_text="Shelter of the Faithful")).to_be_visible()


def test_spellbook_of_a_fighter_is_empty(logged_in_page: Page):
    character = create_via_api(logged_in_page, template="human-fighter")
    CharacterPage(logged_in_page).open_character(character["id"], "spellbook")
    expect(logged_in_page.get_by_test_id("no-spells")).to_contain_text("doesn't cast spells")


def test_spellbook_of_a_wizard(logged_in_page: Page):
    build = autofill(check_via_api(logged_in_page), blank(**{
        "name": "Mira", "class": "wizard", "race": "elf", "subrace": "high-elf",
        "ability_scores": {"method": "standard-array",
                           "base": {"str": 8, "dex": 14, "con": 13, "int": 15, "wis": 12, "cha": 10}}}))
    character = create_via_api(logged_in_page, build=build)
    CharacterPage(logged_in_page).open_character(character["id"], "spellbook")
    expect(logged_in_page.get_by_test_id("stat-spell-dc").locator(".stat-value")).to_have_text("13")
    expect(logged_in_page.get_by_test_id("spell-slots")).to_contain_text("2 × 1st level")
    # 3 wizard cantrips + 1 high elf cantrip + 6 spellbook spells
    expect(logged_in_page.get_by_test_id("spell")).to_have_count(10)


def test_notes_are_saved(logged_in_page: Page):
    character = create_via_api(logged_in_page, template="human-fighter")
    tome = CharacterPage(logged_in_page).open_character(character["id"], "notes")
    expect(tome.note("Ideals")).to_have_value(re.compile(r"^Protection"))
    tome.note("Backstory").fill("Aldric once guarded a dragon's egg by mistake.")
    with logged_in_page.expect_response(lambda r: r.request.method == "PATCH"):
        logged_in_page.get_by_role("button", name="Save notes").click()
    expect(logged_in_page.get_by_test_id("flash-success")).to_have_text("Notes saved.")
    logged_in_page.reload()
    expect(tome.note("Backstory")).to_have_value("Aldric once guarded a dragon's egg by mistake.")


def test_unbuilt_pages_show_their_plans(logged_in_page: Page):
    character = create_via_api(logged_in_page, template="human-fighter")
    tome = CharacterPage(logged_in_page).open_character(character["id"], "roadmaps")
    expect(logged_in_page.get_by_test_id("draft-page")).to_contain_text("up to level 20")
    tome.prev_page.click()
    expect(tome.page_title).to_have_text("Campaigns")


# ------------------------------------------------------------------ build mode and deleting
def test_build_mode_toggle_is_saved(logged_in_page: Page):
    character = create_via_api(logged_in_page, template="human-fighter")
    tome = CharacterPage(logged_in_page).open_character(character["id"])
    expect(tome.build_mode.get_by_label("Easy build")).to_be_checked()
    tome.set_build_mode("Standard build")
    expect(logged_in_page.get_by_test_id("flash-success")).to_have_text("Aldric Vane now uses Standard build.")
    logged_in_page.reload()
    expect(tome.build_mode.get_by_label("Standard build")).to_be_checked()


def test_delete_a_character(logged_in_page: Page):
    create_via_api(logged_in_page, build=blank(name="Keeper"))
    doomed = create_via_api(logged_in_page, build=blank(name="Doomed"))
    tome = CharacterPage(logged_in_page).open_character(doomed["id"])
    tome.delete_button.click()
    expect(tome.delete_dialog).to_contain_text("Delete Doomed?")
    tome.delete_dialog.get_by_role("button", name="Keep it").click()
    expect(tome.delete_dialog).to_be_hidden()

    tome.delete_button.click()
    tome.delete_dialog.get_by_role("button", name="Delete Doomed").click()
    expect(logged_in_page).to_have_url(re.compile(r"/play/characters/my-characters$"))
    expect(logged_in_page.get_by_test_id("flash-info")).to_have_text("Doomed was deleted.")
    my = MyCharactersPage(logged_in_page)
    expect(my.cards).to_have_count(1)
    expect(my.card("Keeper")).to_be_visible()


def test_someone_elses_character_is_not_found(logged_in_page: Page, browser, browser_context_args, create_user):
    other = create_user()
    context = browser.new_context(**browser_context_args)
    other_page = context.new_page()
    LoginPage(other_page).open().login(other["email"], other["password"])
    expect(other_page).to_have_url(re.compile(r"/guild-hall$"))
    secret = create_via_api(other_page, template="human-fighter")
    context.close()

    logged_in_page.goto(f"/play/characters/c/{secret['id']}/sheet")
    expect(logged_in_page.get_by_test_id("character-missing")).to_contain_text("Character not found")


@pytest.mark.parametrize("chapter", ["sheet", "inventory"])
def test_character_pages_fit_a_phone(browser, browser_context_args, user, chapter):
    context = browser.new_context(**{**browser_context_args, "viewport": {"width": 375, "height": 740}})
    page = context.new_page()
    LoginPage(page).open().login(user["email"], user["password"])
    expect(page).to_have_url(re.compile(r"/guild-hall$"))
    character = create_via_api(page, template="human-fighter")
    CharacterPage(page).open_character(character["id"], chapter)
    expect(page.locator("#page-title")).to_be_visible()
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 0
    context.close()
