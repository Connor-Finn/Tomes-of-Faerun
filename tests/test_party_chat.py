"""Party chat in the browser: the enchanted parchment the DM and the players write on.

Like the campaign tests, these use TWO browser contexts: the Dungeon Master in one and a player in
the other. Nobody reloads the page to see new writing: the chat polls the server, so the tests just
wait (with `expect`) for the other person's words to ink in. That's the auto-waiting Playwright is
built around, and it's what makes real-time features testable without sleeps.
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Browser, Page, expect

from conftest import API_HEADERS
from pages import LoginPage, PartiesPage
from pages.sharing_pages import PartyChat


# ------------------------------------------------------------------ helpers
def post(page: Page, url: str, data: dict | None = None) -> dict:
    response = page.request.post(url, data=data or {}, headers=API_HEADERS)
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
def party(logged_in_page: Page, player_page: Page, player: dict) -> dict:
    """A party with Mira in it (set up through each browser's own API session)."""
    party = post(logged_in_page, "/api/parties", {"name": "The Lantern Bearers"})["party"]
    post(logged_in_page, f"/api/parties/{party['id']}/invites", {"email": player["email"]})
    post(player_page, f"/api/parties/{party['id']}/accept")
    return party


# ------------------------------------------------------------------ writing and reading
def test_messages_ink_in_on_the_other_browser(logged_in_page: Page, player_page: Page, party: dict, user: dict):
    dm = PartyChat(logged_in_page).open_dm(party["id"])
    mira = PartyChat(player_page).open_player(party["id"])
    expect(dm.empty).to_have_text("The parchment is blank. Write the first words.")

    dm.write("Welcome, adventurers. We meet at the Yawning Portal at dusk.")
    expect(dm.box).to_have_value("")
    expect(dm.authors).to_have_text(["You"])

    # No reload: Mira's parchment picks the words up on its own
    expect(mira.bodies).to_have_text(["Welcome, adventurers. We meet at the Yawning Portal at dusk."])
    expect(mira.authors).to_have_text([user["name"]])
    expect(mira.messages.first).to_contain_text("Dungeon Master")

    mira.write("I'll bring the lantern oil.")
    expect(dm.bodies).to_have_text([
        "Welcome, adventurers. We meet at the Yawning Portal at dusk.",
        "I'll bring the lantern oil.",
    ])
    expect(dm.authors).to_have_text(["You", "Mira Thorn"])


def test_enter_writes_and_shift_enter_starts_a_new_line(player_page: Page, party: dict):
    chat = PartyChat(player_page).open_player(party["id"])
    chat.box.fill("Roll call:")
    chat.box.press("Shift+Enter")
    chat.box.press_sequentially("Mira, present.")
    expect(chat.messages).to_have_count(0)  # Shift+Enter only adds a line
    chat.box.press("Enter")
    expect(chat.bodies).to_have_text(["Roll call:\nMira, present."])


def test_an_empty_message_is_refused(player_page: Page, party: dict):
    chat = PartyChat(player_page).open_player(party["id"])
    chat.box.fill("   ")
    chat.write_button.click()
    expect(chat.error).to_have_text("Write something first.")
    expect(chat.box).to_have_attribute("aria-invalid", "true")
    expect(chat.messages).to_have_count(0)


def test_the_others_see_who_is_writing(logged_in_page: Page, player_page: Page, party: dict):
    dm = PartyChat(logged_in_page).open_dm(party["id"])
    mira = PartyChat(player_page).open_player(party["id"])
    expect(dm.writing).to_have_text("")

    mira.box.press_sequentially("Has anyone seen my", delay=20)
    expect(dm.writing).to_have_text("Mira Thorn is writing…")
    expect(mira.writing).to_have_text("")  # you never see yourself writing

    mira.box.press("Enter")
    expect(dm.bodies).to_have_text(["Has anyone seen my"])
    expect(dm.writing).to_have_text("")


# ------------------------------------------------------------------ striking messages out
def test_a_struck_message_fades_from_every_page(logged_in_page: Page, player_page: Page, party: dict):
    dm = PartyChat(logged_in_page).open_dm(party["id"])
    mira = PartyChat(player_page).open_player(party["id"])
    mira.write("The password is 'swordfish'.")
    expect(dm.bodies).to_have_text(["The password is 'swordfish'."])

    mira.strike("swordfish")
    expect(mira.dialog).to_have_count(0)
    expect(mira.messages).to_have_count(0)
    expect(dm.messages).to_have_count(0)  # gone from the DM's parchment too, without a reload


def test_the_dm_can_strike_any_message_but_players_only_their_own(
        logged_in_page: Page, player_page: Page, party: dict, user: dict):
    post(logged_in_page, f"/api/parties/{party['id']}/messages", {"body": "Session moved to Friday."})
    post(player_page, f"/api/parties/{party['id']}/messages", {"body": "Something rude about goblins."})

    mira = PartyChat(player_page).open_player(party["id"])
    expect(mira.message("Session moved").get_by_role("button", name="Strike out")).to_have_count(0)
    expect(mira.message("goblins").get_by_role("button", name="Strike out your message")).to_have_count(1)

    dm = PartyChat(logged_in_page).open_dm(party["id"])
    expect(dm.message("goblins").get_by_role("button", name="Strike out Mira Thorn's message")).to_have_count(1)
    dm.strike("goblins")
    expect(dm.bodies).to_have_text(["Session moved to Friday."])
    expect(mira.bodies).to_have_text(["Session moved to Friday."])


# ------------------------------------------------------------------ unread counts and history
def test_unread_messages_are_counted_on_the_party_list(logged_in_page: Page, player_page: Page, party: dict):
    chat = PartyChat(player_page).open_player(party["id"])  # Mira has read the (empty) chat
    expect(chat.empty).to_be_visible()

    post(logged_in_page, f"/api/parties/{party['id']}/messages", {"body": "Did everyone level up?"})
    post(logged_in_page, f"/api/parties/{party['id']}/messages", {"body": "Bring your character sheets."})

    parties = PartiesPage(player_page).open_player()
    card = parties.party_cards.filter(has_text="The Lantern Bearers")
    expect(card.get_by_test_id("unread")).to_have_text("2 unread")

    card.get_by_role("link", name="Open The Lantern Bearers's chat").click()
    expect(chat.bodies).to_have_count(2)
    # A divider marks where the new writing starts
    expect(chat.unread_mark).to_have_text("New since you last looked")
    expect(chat.log.locator("li").nth(0)).to_have_attribute("data-testid", "chat-unread")

    PartiesPage(player_page).open_player()
    expect(card.get_by_test_id("unread")).to_have_count(0)


def test_turn_back_the_page_for_older_messages(logged_in_page: Page, party: dict):
    for n in range(1, 56):
        post(logged_in_page, f"/api/parties/{party['id']}/messages", {"body": f"Entry {n}"})
    chat = PartyChat(logged_in_page).open_dm(party["id"])
    expect(chat.messages).to_have_count(50)  # one page
    expect(chat.bodies.first).to_have_text("Entry 6")
    expect(chat.bodies.last).to_have_text("Entry 55")

    chat.older.click()
    expect(chat.messages).to_have_count(55)
    expect(chat.bodies.first).to_have_text("Entry 1")
    expect(chat.older).to_have_count(0)  # nothing older left


# ------------------------------------------------------------------ who can read it
def test_only_party_members_can_open_the_chat(browser: Browser, browser_context_args: dict, create_user, party: dict):
    stranger = create_user(name="Nosy Neighbour")
    context = browser.new_context(**browser_context_args)
    page = context.new_page()
    LoginPage(page).open().login(stranger["email"], stranger["password"])
    expect(page).to_have_url(re.compile(r"/guild-hall$"))
    page.goto(f"/play/campaigns/parties/{party['id']}")
    expect(page.get_by_test_id("party-missing")).to_contain_text("Party not found")
    expect(page.get_by_test_id("party-chat")).to_have_count(0)
    context.close()


def test_leaving_from_the_party_page(player_page: Page, party: dict):
    chat = PartyChat(player_page).open_player(party["id"])
    expect(player_page.get_by_test_id("party-roster")).to_contain_text("Mira Thorn (you)")
    player_page.get_by_role("button", name="Leave party").click()
    player_page.get_by_role("dialog").get_by_role("button", name="Leave").click()
    expect(player_page).to_have_url(re.compile(r"/play/campaigns/parties$"))
    expect(player_page.get_by_test_id("flash-info").last).to_have_text("You left The Lantern Bearers.")
    chat.open_player(party["id"])
    expect(player_page.get_by_test_id("party-missing")).to_be_visible()
