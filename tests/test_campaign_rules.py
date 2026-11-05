"""Character rules in campaigns, in the browser, from both sides of the DM screen.

The DM sets the campaign's rules in the control panel and looks after each player's character
there (levels, XP, items, spells, notes). The player levels up through the guided Level Up, adds the
XP they earn, and uses up the items they're given. Rolled ability scores are made in the builder.
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Browser, Page, expect

from builds import aldric, autofill, blank
from conftest import API_HEADERS
from pages import BuilderPage, CampaignCharacterPage, ControlPanelPage, LevelUpPage, LoginPage


def post(page: Page, url: str, data: dict | None = None, method: str = "post") -> dict:
    response = getattr(page.request, method)(url, data=data or {}, headers=API_HEADERS)
    assert response.ok, response.text()
    return response.json()


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
    party = post(logged_in_page, "/api/parties", {"name": "The Lantern Bearers"})["party"]
    post(logged_in_page, f"/api/parties/{party['id']}/invites", {"email": player["email"]})
    post(player_page, f"/api/parties/{party['id']}/accept")
    campaign = post(logged_in_page, "/api/campaigns", {"name": "The Whispering Dead", "status": "active"})["campaign"]
    post(logged_in_page, f"/api/campaigns/{campaign['id']}", {"party_id": party["id"]}, method="patch")
    return {"id": campaign["id"], "url": f"/api/campaigns/{campaign['id']}"}


def bring(page: Page, table: dict, build: dict | None = None, name: str = "Aldric Vane") -> dict:
    character = post(page, "/api/characters", {"build": {**(build or aldric()), "name": name}})["character"]
    return post(page, f"{table['url']}/instance", {"character_id": character["id"]})["instance"]


def check(page: Page):
    return lambda b: post(page, "/api/characters/check", {"build": b})


# ------------------------------------------------------------------ campaign rules and XP
def test_xp_levelling_opens_level_up_at_the_threshold(table: dict, logged_in_page: Page, player_page: Page):
    bring(player_page, table)
    panel = ControlPanelPage(logged_in_page).open(table["id"])
    expect(panel.page_title).to_have_text("Control panel")
    panel.set_levelling("Experience points")
    panel.hp_method("Average").uncheck()
    panel.hp_method("Maximum").check()
    panel.save_rules.click()
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Campaign rules saved.")

    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    expect(you.level_controls).to_contain_text("Levelling: experience points")
    expect(you.xp_total).to_have_text("0 XP · level 2 at 300 XP")
    expect(you.level_up_blocked).to_have_text("Aldric Vane needs 300 more XP to reach level 2.")
    you.add_xp(120)
    expect(you.xp_total).to_contain_text("120 XP")
    you.add_xp(200)

    # Crossing 300 XP opens the level-up straight away
    expect(player_page).to_have_url(re.compile(rf"/play/campaigns/c/{table['id']}/character/level-up$"))
    expect(player_page.get_by_test_id("flash-success").last).to_contain_text("Level 2 is ready!")
    levelling = LevelUpPage(player_page)
    expect(levelling.hp_option("average")).to_have_count(0)   # the DM didn't allow it
    expect(levelling.hp_option("max")).to_contain_text("10 on the die")
    levelling.roll_hp()
    expect(levelling.hp_option("roll")).to_contain_text(re.compile(r"\d+ on the die"))
    rolled = re.search(r"\d+ on the die", levelling.hp_option("roll").inner_text()).group(0)
    player_page.reload()   # the roll is kept: no rerolls
    expect(levelling.hp_option("roll")).to_contain_text(rolled)
    levelling.choose_hp("roll")
    levelling.confirm()
    expect(player_page.locator(".page-summary").first).to_contain_text("Level 2 Human Fighter")


def test_the_dm_raises_a_level(table: dict, logged_in_page: Page, player_page: Page):
    instance = bring(player_page, table)
    panel = ControlPanelPage(logged_in_page).open(table["id"])
    panel.manage("Aldric Vane")
    panel.set_level(3)
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Aldric Vane can level up to level 3.")
    expect(panel.level_panel).to_contain_text("2 level-ups waiting for Mira Thorn")
    panel.open(table["id"])
    expect(panel.players.first).to_contain_text("2 level-ups waiting")

    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    expect(you.levels_owed).to_have_text("2 level-ups are ready, one at a time.")
    assert instance["id"]


# ------------------------------------------------------------------ items
def test_the_dm_hands_out_items_and_the_player_uses_them(table: dict, logged_in_page: Page, player_page: Page):
    instance = bring(player_page, table)
    panel = ControlPanelPage(logged_in_page).open(table["id"], instance["id"])
    panel.give("Potion of Healing", 2)
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("You gave 2 × Potion of Healing to Aldric Vane.")
    expect(panel.inventory.filter(has_text="Potion of Healing")).to_contain_text("From you")

    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    you.tab("Inventory")
    potion = you.item("Potion of Healing")
    expect(potion).to_contain_text("From your DM")
    potion.get_by_role("button", name="Use up or drop one Potion of Healing").click()
    expect(player_page.get_by_test_id("flash-success").last).to_have_text("One Potion of Healing was used up.")
    expect(potion.locator("td").nth(2)).to_have_text("1")
    expect(you.used_items).to_contain_text("1 × Potion of Healing")
    you.used_items.get_by_role("button", name="Put one Potion of Healing back").click()
    expect(potion.locator("td").nth(2)).to_have_text("2")
    expect(you.used_items).to_have_count(0)
    # Only the DM adds items in a campaign: the player has no catalogue here
    expect(player_page.get_by_role("link", name="Change items")).to_have_count(0)


# ------------------------------------------------------------------ spells
def test_the_dm_grants_a_wizard_a_spell_to_copy(table: dict, logged_in_page: Page, player_page: Page):
    wizard = autofill(check(player_page), blank(**{"class": "wizard"}))
    instance = bring(player_page, table, wizard, name="Elara")
    book = wizard["choices"]["spells:spellbook"]
    spell, name = next((i, n) for i, n in (("identify", "Identify"), ("shield", "Shield"), ("sleep", "Sleep"))
                       if i not in book)

    panel = ControlPanelPage(logged_in_page).open(table["id"], instance["id"])
    panel.grant(name)
    expect(logged_in_page.get_by_test_id("flash-success").last).to_contain_text("They can copy it into their spellbook.")
    expect(panel.granted).to_contain_text("Not copied yet")

    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    you.tab("Spellbook")
    expect(you.spells_to_copy).to_contain_text(name)
    you.spells_to_copy.get_by_role("button", name="Copy into spellbook").click()
    expect(player_page.get_by_test_id("flash-success").last).to_have_text(f"{name} was copied into Elara's spellbook.")
    expect(player_page.get_by_test_id("spell").filter(has_text=name)).to_contain_text("Copied into your spellbook")


def test_prepared_spells_change_during_play(table: dict, player_page: Page):
    cleric = autofill(check(player_page), blank(**{"class": "cleric", "subclass": "life"}))
    bring(player_page, table, cleric, name="Sister Ama")
    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    you.tab("Spellbook")
    player_page.get_by_role("button", name="Change prepared spells").click()
    editor = player_page.get_by_test_id("prepared-editor")
    expect(editor).to_be_visible()
    player_page.get_by_role("button", name="Save prepared spells").click()
    expect(player_page.get_by_test_id("flash-success").last).to_have_text("Prepared spells changed.")


# ------------------------------------------------------------------ rolled ability scores
def roll_method(page: Page) -> None:
    """The radio only turns on once the server has answered with the rolls, so click and wait."""
    radio = page.get_by_role("radio", name="Rolled (4d6, drop the lowest)")
    radio.click()
    expect(radio).to_be_checked()


def test_roll_ability_scores_in_the_builder(logged_in_page: Page):
    builder = BuilderPage(logged_in_page).open_new()
    builder.go_to("Ability scores")
    roll_method(logged_in_page)
    rolled = logged_in_page.get_by_test_id("rolled-scores")
    expect(rolled).to_contain_text("Your rolls:")
    expect(logged_in_page.get_by_test_id("rolled-dice")).to_contain_text("dropped")
    rolls = re.findall(r"\d+", rolled.locator("strong").inner_text())
    assert len(rolls) == 6

    # Switching away and back keeps the same rolls: no rerolls
    logged_in_page.get_by_role("radio", name="Standard array").click()
    roll_method(logged_in_page)
    expect(rolled.locator("strong")).to_have_text(", ".join(rolls))

    for ability, value in zip(("Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"), rolls):
        logged_in_page.get_by_label(f"{ability} score").select_option(value)
    expect(logged_in_page.get_by_test_id("score-str")).not_to_have_text("—")


# ------------------------------------------------------------------ warnings, not errors
def test_rule_bending_gear_shows_a_warning(table: dict, logged_in_page: Page, player_page: Page):
    wizard = autofill(check(player_page), blank(**{"class": "wizard"}))
    instance = bring(player_page, table, wizard, name="Elara")
    panel = ControlPanelPage(logged_in_page).open(table["id"], instance["id"])
    panel.give("Chain Mail")
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("You gave Chain Mail to Elara.")

    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    expect(you.warnings).to_have_count(0)
    you.tab("Inventory")
    player_page.get_by_role("button", name="Wear Chain Mail").click()
    expect(player_page.get_by_test_id("flash-success").last).to_have_text("Wearing Chain Mail.")
    you.tab("Sheet")
    expect(you.warnings).to_contain_text("You aren't proficient with Chain Mail")
