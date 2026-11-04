"""Campaigns in the browser, from both sides of the DM screen.

Most tests here use TWO browser contexts at once: the Dungeon Master in one and a player in the
other, each with their own cookies, like two people on two computers. That's how the invite →
accept → play loop is tested end to end.
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Browser, Page, expect

from builds import aldric, autofill
from conftest import API_HEADERS
from pages import (CampaignCharacterPage, CampaignTomePage, CharacterPage, DmCampaignsPage, GuildHallPage, LoginPage,
                   PartiesPage)


# ------------------------------------------------------------------ helpers
def post(page: Page, url: str, data: dict | None = None, method: str = "post") -> dict:
    """Set up data with that browser's own session (fast, no clicking)."""
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
    """A campaign with a party, and the player in it (set up through the API)."""
    party = post(logged_in_page, "/api/parties", {"name": "The Lantern Bearers"})["party"]
    post(logged_in_page, f"/api/parties/{party['id']}/invites", {"email": player["email"]})
    post(player_page, f"/api/parties/{party['id']}/accept")
    campaign = post(logged_in_page, "/api/campaigns", {
        "name": "The Whispering Dead", "status": "active",
        "description": "Something stirs in the crypts beneath Neverwinter."})["campaign"]
    post(logged_in_page, f"/api/campaigns/{campaign['id']}", {"party_id": party["id"]}, method="patch")
    return {"party": party, "campaign": campaign, "id": campaign["id"]}


def give_character(page: Page, name: str = "Aldric Vane") -> dict:
    return post(page, "/api/characters", {"build": {**aldric(), "name": name}})["character"]


# ------------------------------------------------------------------ DM: campaigns
def test_start_a_campaign_from_the_guild_hall(logged_in_page: Page):
    GuildHallPage(logged_in_page).open().switch_to("dm").open_tome("Campaigns")
    campaigns = DmCampaignsPage(logged_in_page)
    expect(campaigns.page_title).to_have_text("Your campaigns")
    expect(campaigns.empty).to_be_visible()

    tome = campaigns.start("The Whispering Dead")
    expect(logged_in_page).to_have_url(re.compile(r"/dm/campaigns/c/\d+/overview$"))
    expect(logged_in_page.get_by_test_id("flash-success").last).to_contain_text("The Whispering Dead is ready.")
    expect(tome.title).to_have_text("The Whispering Dead")
    expect(tome.entries).to_have_text(["Overview", "Party", "Session log", "Encounters", "DM notes"])
    expect(tome.status).to_have_text("Planning")


def test_a_campaign_needs_a_name(logged_in_page: Page):
    campaigns = DmCampaignsPage(logged_in_page).open()
    campaigns.start_button.click()
    expect(campaigns.name_error).to_have_text("Give the campaign a name.")
    expect(campaigns.new_name).to_have_attribute("aria-invalid", "true")


def test_write_the_overview(logged_in_page: Page):
    campaign = post(logged_in_page, "/api/campaigns", {"name": "Untitled"})["campaign"]
    tome = CampaignTomePage(logged_in_page).open_dm(campaign["id"])
    expect(tome.save_overview).to_be_disabled()  # nothing to save yet
    tome.name.fill("Save the Princess")
    tome.status_select.select_option(label="Active")
    tome.description.fill("A rescue that isn't what it seems.")
    tome.save_overview.click()

    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Overview saved.")
    expect(tome.title).to_have_text("Save the Princess")
    expect(tome.status).to_have_text("Active")
    card = DmCampaignsPage(logged_in_page).open().card("Save the Princess")
    expect(card).to_contain_text("A rescue that isn't what it seems.")
    expect(card.get_by_test_id("campaign-status")).to_have_text("Active")


def test_delete_a_campaign(logged_in_page: Page):
    campaign = post(logged_in_page, "/api/campaigns", {"name": "Doomed"})["campaign"]
    tome = CampaignTomePage(logged_in_page).open_dm(campaign["id"])
    tome.delete_button.click()
    dialog = logged_in_page.get_by_role("dialog")
    expect(dialog).to_contain_text("Your party, your bestiary collections and the players' own characters are kept.")
    dialog.get_by_role("button", name="Delete").click()
    expect(logged_in_page).to_have_url(re.compile(r"/dm/campaigns/campaigns$"))
    expect(logged_in_page.get_by_test_id("flash-info").last).to_have_text("Doomed was deleted.")


def test_keep_a_session_log(logged_in_page: Page):
    campaign = post(logged_in_page, "/api/campaigns", {"name": "The Whispering Dead"})["campaign"]
    tome = CampaignTomePage(logged_in_page).open_dm(campaign["id"], "sessions")
    expect(tome.no_sessions).to_be_visible()

    tome.add_session("The crypt door", "2026-10-04", "A sealed door under the temple.")
    tome.add_session("Bones in the dark", "2026-10-11", "Two skeletons and a lich's diary.")
    expect(tome.session_titles).to_have_text(["Bones in the dark", "The crypt door"])  # newest first
    expect(tome.sessions.first).to_contain_text("11 Oct 2026")

    tome.edit_session("The crypt door")
    tome.session_title.fill("The sealed crypt door")
    tome.save_session_button.click()
    expect(tome.session_titles).to_have_text(["Bones in the dark", "The sealed crypt door"])

    tome.edit_session("Bones in the dark")
    logged_in_page.get_by_role("button", name="Delete session").click()
    logged_in_page.get_by_role("dialog").get_by_role("button", name="Delete").click()
    expect(tome.session_titles).to_have_text(["The sealed crypt door"])


def test_a_session_needs_a_title(logged_in_page: Page):
    campaign = post(logged_in_page, "/api/campaigns", {"name": "The Whispering Dead"})["campaign"]
    tome = CampaignTomePage(logged_in_page).open_dm(campaign["id"], "sessions")
    tome.add_session_button.click()
    expect(logged_in_page.get_by_test_id("error-title")).to_have_text("Give the session a title.")


def test_add_bestiary_collections_as_encounters(logged_in_page: Page):
    campaign = post(logged_in_page, "/api/campaigns", {"name": "The Whispering Dead"})["campaign"]
    crypt = post(logged_in_page, "/api/bestiary/collections", {"name": "Crypt guardians"})["collection"]
    post(logged_in_page, f"/api/bestiary/collections/{crypt['id']}/monsters", {"monster": "skeleton", "count": 4})
    post(logged_in_page, "/api/bestiary/collections", {"name": "Goblin ambush"})

    tome = CampaignTomePage(logged_in_page).open_dm(campaign["id"], "encounters")
    expect(tome.no_encounters).to_be_visible()
    tome.add_encounter("Crypt guardians (4 monsters, 200 XP)")
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text(
        "Crypt guardians was added to The Whispering Dead's encounters.")
    expect(tome.encounter("Crypt guardians")).to_contain_text("4 monsters · 200 XP")
    expect(tome.encounter_totals).to_have_text("1 encounter · 200 XP in all")
    # an attached collection isn't offered twice
    expect(tome.collection_select.locator("option")).to_have_text(["Choose a collection…", "Goblin ambush (0 monsters, 0 XP)"])

    # the encounter links to the collection in the bestiary
    tome.encounter("Crypt guardians").get_by_role("link").click()
    expect(logged_in_page).to_have_url(re.compile(rf"/dm/tomes/collections/{crypt['id']}$"))
    logged_in_page.go_back()

    tome.take_off("Crypt guardians")
    expect(logged_in_page.get_by_test_id("flash-info").last).to_contain_text("The collection is still in your bestiary.")
    expect(tome.no_encounters).to_be_visible()


def test_private_dm_notes(logged_in_page: Page):
    campaign = post(logged_in_page, "/api/campaigns", {"name": "The Whispering Dead"})["campaign"]
    tome = CampaignTomePage(logged_in_page).open_dm(campaign["id"], "notes")
    tome.dm_notes.fill("The high priest is the lich's servant.")
    tome.save_notes.click()
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Notes saved.")
    logged_in_page.reload()
    expect(tome.dm_notes).to_have_value("The high priest is the lich's servant.")


# ------------------------------------------------------------------ parties: two browsers
def test_invite_a_player_who_accepts(logged_in_page: Page, player_page: Page, player: dict, user: dict):
    dm = PartiesPage(logged_in_page).open_dm().form("The Lantern Bearers")
    expect(logged_in_page).to_have_url(re.compile(r"/dm/campaigns/parties/\d+$"))
    dm.invite(player["email"])
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Mira Thorn was invited to The Lantern Bearers.")
    expect(dm.invited).to_contain_text("Mira Thorn")

    # Meanwhile, in the player's browser...
    mine = PartiesPage(player_page).open_player()
    expect(mine.invitations).to_contain_text(f"{user['name']} invited you")
    mine.accept("The Lantern Bearers")
    expect(player_page.get_by_test_id("flash-success").last).to_have_text("You joined The Lantern Bearers.")
    expect(mine.party_cards).to_contain_text(f"Led by {user['name']} · 1 player")

    # ...and back in the DM's, Mira is now a member
    logged_in_page.reload()
    expect(dm.members).to_contain_text("Mira Thorn")
    expect(dm.invited).to_have_count(0)


def test_invite_errors(logged_in_page: Page, user: dict):
    dm = PartiesPage(logged_in_page).open_dm().form("The Lantern Bearers")
    dm.invite("nobody_here@example.com")
    expect(dm.invite_error).to_have_text("No adventurer has signed up with that email.")
    dm.invite(user["email"])
    expect(dm.invite_error).to_have_text("You're the party's Dungeon Master, so you don't need an invitation.")


def test_decline_an_invitation(logged_in_page: Page, player_page: Page, player: dict):
    party = post(logged_in_page, "/api/parties", {"name": "The Lantern Bearers"})["party"]
    post(logged_in_page, f"/api/parties/{party['id']}/invites", {"email": player["email"]})
    mine = PartiesPage(player_page).open_player()
    mine.decline("The Lantern Bearers")
    expect(player_page.get_by_test_id("flash-info").last).to_have_text("You declined the invitation to The Lantern Bearers.")
    expect(mine.invitations).to_have_count(0)
    expect(mine.no_parties).to_be_visible()


def test_attach_the_party_to_a_campaign(logged_in_page: Page, player_page: Page, player: dict):
    party = post(logged_in_page, "/api/parties", {"name": "The Lantern Bearers"})["party"]
    post(logged_in_page, f"/api/parties/{party['id']}/invites", {"email": player["email"]})
    post(player_page, f"/api/parties/{party['id']}/accept")
    campaign = post(logged_in_page, "/api/campaigns", {"name": "The Whispering Dead"})["campaign"]

    tome = CampaignTomePage(logged_in_page).open_dm(campaign["id"], "party")
    expect(tome.attached_party).to_have_text("No party is playing this campaign yet.")
    tome.attach_party("The Lantern Bearers (1 player)")
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text(
        "The Lantern Bearers is now playing The Whispering Dead.")
    expect(tome.player_card("Mira Thorn")).to_contain_text("Hasn't brought a character yet.")

    # The campaign now shows up for the player
    player_page.goto("/play/campaigns/current")
    expect(player_page.get_by_test_id("campaign-card")).to_contain_text("The Whispering Dead")
    expect(player_page.get_by_test_id("my-character")).to_have_text("Bring a character")


def test_leave_a_party(table: dict, player_page: Page):
    PartiesPage(player_page).open_player().leave("The Lantern Bearers")
    expect(player_page.get_by_test_id("flash-info").last).to_have_text("You left The Lantern Bearers.")
    player_page.goto(f"/play/campaigns/c/{table['id']}/overview")
    expect(CampaignTomePage(player_page).missing).to_be_visible()


# ------------------------------------------------------------------ the player's edition
def test_players_read_their_own_edition(table: dict, logged_in_page: Page, player_page: Page, user: dict):
    post(logged_in_page, f"/api/campaigns/{table['id']}/sessions", {"played_on": "2026-10-04", "title": "The crypt door"})
    tome = CampaignTomePage(player_page).open_player(table["id"])
    expect(tome.entries).to_have_text(["Overview", "Your character", "Party", "Session log"])  # no encounters or DM notes
    expect(tome.overview_dm).to_have_text(user["name"])
    expect(tome.overview_text).to_have_text("Something stirs in the crypts beneath Neverwinter.")
    tome.go_to("Session log")
    expect(tome.session_titles).to_have_text(["The crypt door"])
    expect(player_page.get_by_role("button", name="Add to the log")).to_have_count(0)


def test_a_player_opening_the_dm_link_gets_their_edition(table: dict, player_page: Page):
    player_page.goto(f"/dm/campaigns/c/{table['id']}/notes")
    expect(player_page).to_have_url(re.compile(rf"/play/campaigns/c/{table['id']}/overview$"))


def test_strangers_cant_open_a_campaign(table: dict, browser: Browser, browser_context_args: dict, create_user):
    stranger = create_user()
    context = browser.new_context(**browser_context_args)
    page = context.new_page()
    LoginPage(page).open().login(stranger["email"], stranger["password"])
    page.goto(f"/play/campaigns/c/{table['id']}/overview")
    expect(CampaignTomePage(page).missing).to_contain_text("Campaign not found")
    context.close()


def test_bring_a_character_to_the_campaign(table: dict, player_page: Page):
    give_character(player_page)
    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    expect(you.bring_button).to_be_disabled()
    you.bring("Aldric Vane")
    expect(player_page.get_by_test_id("flash-success").last).to_have_text("Aldric Vane joined The Whispering Dead.")
    expect(you.page_title).to_have_text("Aldric Vane")
    expect(you.hp_bar).to_have_text("12/12 HP")
    expect(you.stat("ac")).to_have_text("18")
    expect(you.origin).to_contain_text("copied from Aldric Vane in the Character Manager, which stays at level 1")

    you.tab("Inventory")
    expect(player_page.get_by_test_id("inventory")).to_contain_text("Chain Mail")
    expect(player_page.get_by_role("link", name="Change items")).to_have_count(0)  # read-only here


def test_drafts_cant_be_brought(table: dict, player_page: Page):
    post(player_page, "/api/characters", {"build": {"name": "Half done", "level": 1}})
    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    expect(you.no_ready).to_contain_text("You need a finished character first.")


def test_track_hit_points_and_rest(table: dict, player_page: Page):
    character = give_character(player_page)
    post(player_page, f"/api/campaigns/{table['id']}/instance", {"character_id": character["id"]})
    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    you.set_hp(3, 5)
    expect(player_page.get_by_test_id("flash-success").last).to_have_text("Hit points updated.")
    expect(you.hp_bar).to_have_text("3/12 HP + 5 temp")
    expect(you.hp_bar.locator(".hp-fill")).to_have_class(re.compile(r"\blow\b"))  # the bar turns red

    you.long_rest.click()
    expect(player_page.get_by_test_id("flash-success").last).to_have_text("Aldric Vane took a long rest.")
    expect(you.hp_bar).to_have_text("12/12 HP")


def test_level_up_in_the_campaign_only(table: dict, player_page: Page):
    character = give_character(player_page)
    post(player_page, f"/api/campaigns/{table['id']}/instance", {"character_id": character["id"]})
    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    you.level_up.click()

    expect(player_page).to_have_url(re.compile(rf"/play/campaigns/c/{table['id']}/character/edit$"))
    expect(player_page.get_by_role("heading", level=1)).to_have_text("Levelling up Aldric Vane")
    expect(player_page.get_by_test_id("campaign-builder-note")).to_contain_text(
        "Your character in the Character Manager stays as it is.")
    player_page.get_by_label("Level", exact=True).select_option("2")
    expect(player_page.get_by_test_id("builder-status")).to_have_text(re.compile("Complete|choice"))
    player_page.get_by_role("button", name="Save changes").click()

    expect(player_page).to_have_url(re.compile(rf"/play/campaigns/c/{table['id']}/character$"))
    expect(player_page.get_by_test_id("flash-success").last).to_have_text("Aldric Vane is now level 2 in The Whispering Dead.")
    expect(player_page.locator(".page-summary").first).to_contain_text("Level 2 Human Fighter")

    # The base character didn't move
    sheet = CharacterPage(player_page).open_character(character["id"])
    expect(sheet.stat("hp")).to_have_text("12")
    sheet.go_to("Campaigns")
    expect(player_page.get_by_test_id("character-campaign")).to_contain_text("Level 2 Human Fighter")


def test_an_unfinished_level_up_is_refused(table: dict, player_page: Page):
    character = give_character(player_page)
    post(player_page, f"/api/campaigns/{table['id']}/instance", {"character_id": character["id"]})
    player_page.goto(f"/play/campaigns/c/{table['id']}/character/edit")
    player_page.get_by_label("Level", exact=True).select_option("3")  # fighters pick a subclass at 3
    player_page.get_by_role("button", name="Save changes").click()
    expect(player_page.get_by_test_id("builder-errors")).to_contain_text("Choose a subclass.")


def test_the_dm_reads_the_sheet_and_leaves_a_note(table: dict, logged_in_page: Page, player_page: Page):
    character = give_character(player_page)
    post(player_page, f"/api/campaigns/{table['id']}/instance", {"character_id": character["id"]})

    tome = CampaignTomePage(logged_in_page).open_dm(table["id"], "party")
    card = tome.player_card("Mira Thorn")
    expect(card).to_contain_text("Level 1 Human Fighter")
    card.get_by_role("link", name="Aldric Vane").click()

    sheet = CampaignCharacterPage(logged_in_page)
    expect(sheet.page_title).to_have_text("Aldric Vane")
    expect(sheet.update_hp).to_have_count(0)  # the DM can read, not change
    expect(sheet.level_up).to_have_count(0)
    sheet.note_box.fill("The ghoul's claw left a mark that won't heal.")
    sheet.save_note.click()
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Your note on Aldric Vane was saved.")

    # The player sees the note on their character
    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    expect(you.dm_note).to_contain_text("A note from your Dungeon Master")
    expect(you.dm_note).to_contain_text("The ghoul's claw left a mark that won't heal.")


def test_leave_the_campaign_with_a_character(table: dict, player_page: Page):
    character = give_character(player_page)
    post(player_page, f"/api/campaigns/{table['id']}/instance", {"character_id": character["id"]})
    you = CampaignCharacterPage(player_page).open_player(table["id"], "character")
    you.leave_button.click()
    player_page.get_by_role("dialog").get_by_role("button", name="Leave").click()
    expect(player_page.get_by_test_id("flash-info").last).to_contain_text("Aldric Vane left The Whispering Dead.")
    expect(you.bring_form).to_be_visible()
