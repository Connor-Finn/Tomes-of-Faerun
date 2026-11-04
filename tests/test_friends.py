"""Friends and joining parties in the browser.

Every story here has two people in it, so the tests open TWO browser contexts: separate cookie jars,
like two players on two computers. `logged_in_page` is the Dungeon Master (or the first player) and
`mira_page` is Mira. Set-up that isn't the point of a test goes through the API, so each test only
clicks through the part it's checking.
"""
from __future__ import annotations

import re
import uuid

import pytest
from playwright.sync_api import Browser, Page, expect

from conftest import API_HEADERS
from pages import FindPartyPage, FriendsPage, JoinRequestsPage, LoginPage, PartiesPage


def unique(name: str) -> str:
    """Tests share one database, so give everyone a name only this test uses."""
    return f"{name} {uuid.uuid4().hex[:5]}"


def post(page: Page, url: str, data: dict | None = None) -> dict:
    response = page.request.post(url, data=data or {}, headers=API_HEADERS)
    assert response.ok, response.text()
    return response.json()


def browser_for(browser: Browser, browser_context_args: dict, someone: dict):
    context = browser.new_context(**browser_context_args)
    page = context.new_page()
    LoginPage(page).open().login(someone["email"], someone["password"])
    expect(page).to_have_url(re.compile(r"/guild-hall$"))
    return context, page


@pytest.fixture
def mira(create_user) -> dict:
    return create_user(name=unique("Mira Thorn"))


@pytest.fixture
def mira_page(browser: Browser, browser_context_args: dict, mira: dict) -> Page:
    """A second browser, logged in as Mira."""
    context, page = browser_for(browser, browser_context_args, mira)
    yield page
    context.close()


def befriend(a: Page, b: Page, b_id: int, a_id: int) -> None:
    post(a, "/api/friends", {"user_id": b_id})
    post(b, f"/api/friends/{a_id}/accept")


# ------------------------------------------------------------------ friends
def test_send_a_friend_request_and_it_is_accepted(logged_in_page: Page, mira_page: Page, user: dict, mira: dict):
    me = FriendsPage(logged_in_page).open()
    expect(me.no_friends).to_be_visible()
    me.add(mira["name"])
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text(f"Friend request sent to {mira['name']}.")
    expect(me.result(mira["name"])).to_contain_text("Request sent")
    expect(me.sent).to_have_text([re.compile(mira["name"])])

    # Mira, on her own computer, finds the request waiting and accepts it
    theirs = FriendsPage(mira_page).open()
    expect(theirs.requests).to_have_count(1)
    expect(theirs.requests.first).to_contain_text(user["name"])
    theirs.accept(user["name"])
    expect(mira_page.get_by_test_id("flash-success").last).to_have_text(f"You and {user['name']} are now friends.")
    expect(theirs.requests).to_have_count(0)
    expect(theirs.friends).to_have_text([re.compile(user["name"])])

    me.open()
    expect(me.friends).to_have_text([re.compile(mira["name"])])
    expect(me.sent).to_have_count(0)
    me.find(mira["name"])
    expect(me.result(mira["name"])).to_contain_text("Friends")


def test_search_needs_two_letters_and_says_when_nobody_matches(logged_in_page: Page):
    page = FriendsPage(logged_in_page).open()
    page.find("x")
    expect(logged_in_page.get_by_text("Type at least two letters.")).to_be_visible()
    page.find("Nobody-has-this-name")
    expect(page.no_results).to_have_text("No adventurer goes by that name.")


def test_search_never_finds_people_by_email(logged_in_page: Page, mira: dict):
    page = FriendsPage(logged_in_page).open()
    page.find(mira["email"])
    expect(page.no_results).to_be_visible()


def test_decline_a_request(logged_in_page: Page, mira_page: Page, user: dict, mira: dict):
    post(logged_in_page, "/api/friends", {"user_id": mira["id"]})
    theirs = FriendsPage(mira_page).open()
    theirs.decline(user["name"])
    expect(mira_page.get_by_test_id("flash-info").last).to_have_text(f"You declined {user['name']}'s friend request.")
    expect(theirs.requests).to_have_count(0)
    expect(FriendsPage(logged_in_page).open().sent).to_have_count(0)


def test_cancel_a_request_you_sent(logged_in_page: Page, mira: dict):
    post(logged_in_page, "/api/friends", {"user_id": mira["id"]})
    page = FriendsPage(logged_in_page).open()
    page.cancel(mira["name"])
    expect(page.sent).to_have_count(0)
    page.find(mira["name"])
    expect(page.result(mira["name"]).get_by_role("button", name=f"Add {mira['name']} as a friend")).to_be_visible()


def test_answering_from_the_search_results(logged_in_page: Page, mira_page: Page, user: dict, mira: dict):
    post(mira_page, "/api/friends", {"user_id": user["id"]})
    page = FriendsPage(logged_in_page).open()
    page.find(mira["name"])
    page.result(mira["name"]).get_by_role("button", name=f"Accept {mira['name']}'s friend request").click()
    expect(page.result(mira["name"])).to_contain_text("Friends")
    expect(page.friends).to_have_count(1)


def test_remove_a_friend(logged_in_page: Page, mira_page: Page, user: dict, mira: dict):
    befriend(logged_in_page, mira_page, mira["id"], user["id"])
    page = FriendsPage(logged_in_page).open()
    page.unfriend(mira["name"])
    expect(logged_in_page.get_by_test_id("flash-info").last).to_have_text(f"You and {mira['name']} are no longer friends.")
    expect(page.no_friends).to_be_visible()
    expect(FriendsPage(mira_page).open().no_friends).to_be_visible()


# ------------------------------------------------------------------ public parties and join requests
@pytest.fixture
def public_party(logged_in_page: Page) -> dict:
    return post(logged_in_page, "/api/parties", {"name": unique("The Lantern Bearers"), "visibility": "public",
                                                  "description": "A Friday night table for new players."})["party"]


def test_ask_to_join_a_public_party_and_the_dm_says_yes(logged_in_page: Page, mira_page: Page, user: dict,
                                                        mira: dict, public_party: dict):
    name = public_party["name"]
    board = FindPartyPage(mira_page).open()
    board.search.fill(name)
    expect(board.parties).to_have_count(1)
    expect(board.party(name)).to_contain_text(f"Led by {user['name']} · 0 players")
    expect(board.party(name)).to_contain_text("A Friday night table for new players.")
    board.ask_to_join(name, note="I play a halfling bard.")
    expect(mira_page.get_by_test_id("flash-success").last).to_have_text(f"You asked to join {name}. {user['name']} will decide.")
    expect(board.party(name).get_by_test_id("standing")).to_have_text("Request sent")

    # The DM sees the request counted on their party list, then answers it
    dm_parties = PartiesPage(logged_in_page).open_dm()
    expect(dm_parties.party_cards.filter(has_text=name).get_by_test_id("request-count")).to_have_text("1 join request")
    requests = JoinRequestsPage(logged_in_page).open()
    expect(requests.request(mira["name"])).to_contain_text(f"{mira['name']} asked to join")
    expect(requests.request(mira["name"])).to_contain_text("“I play a halfling bard.”")
    requests.accept(mira["name"])
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text(f"{mira['name']} joined {name}.")
    expect(requests.empty).to_be_visible()

    # Mira is in: no invitation to accept, because she asked
    board.open()
    board.search.fill(name)
    expect(board.party(name).get_by_role("link", name="You're in this party")).to_be_visible()
    player_parties = PartiesPage(mira_page).open_player()
    expect(player_parties.party_cards.filter(has_text=name)).to_have_count(1)
    expect(player_parties.invitations).to_have_count(0)


def test_the_dm_declines_from_the_party_page(logged_in_page: Page, mira_page: Page, mira: dict, public_party: dict):
    post(mira_page, f"/api/parties/{public_party['id']}/requests", {"message": "Room for one more?"})
    logged_in_page.goto(f"/dm/campaigns/parties/{public_party['id']}")
    asking = logged_in_page.get_by_test_id("party-requests")
    expect(asking.get_by_test_id("join-request")).to_contain_text("Room for one more?")
    asking.get_by_role("button", name=f"Decline {mira['name']}").click()
    expect(logged_in_page.get_by_test_id("flash-info").last).to_have_text(f"You turned down {mira['name']}'s request.")
    expect(asking).to_have_count(0)

    board = FindPartyPage(mira_page).open()
    board.search.fill(public_party["name"])
    expect(board.party(public_party["name"]).get_by_role("button", name=f"Ask to join {public_party['name']}")).to_be_visible()


def test_withdraw_a_request(logged_in_page: Page, mira_page: Page, public_party: dict):
    name = public_party["name"]
    post(mira_page, f"/api/parties/{public_party['id']}/requests")
    board = FindPartyPage(mira_page).open()
    board.search.fill(name)
    board.withdraw(name)
    expect(mira_page.get_by_test_id("flash-info").last).to_have_text(f"You withdrew your request to join {name}.")
    expect(board.party(name).get_by_role("button", name=f"Ask to join {name}")).to_be_visible()
    expect(JoinRequestsPage(logged_in_page).open().empty).to_be_visible()


def test_private_parties_stay_off_the_notice_board(logged_in_page: Page, mira_page: Page):
    hidden = post(logged_in_page, "/api/parties", {"name": unique("The Quiet Few"), "visibility": "private"})["party"]
    board = FindPartyPage(mira_page).open()
    board.search.fill(hidden["name"])
    expect(board.empty).to_have_text("No public party matches.")

    # The DM turns it public on the party page, and it goes up on the board
    logged_in_page.goto(f"/dm/campaigns/parties/{hidden['id']}")
    logged_in_page.get_by_test_id("party-visibility").get_by_label("Public").click()  # saved, then re-drawn
    expect(logged_in_page.get_by_test_id("party-visibility").get_by_label("Public")).to_be_checked()
    board.open()
    board.search.fill(hidden["name"])
    expect(board.parties).to_have_count(1)


# ------------------------------------------------------------------ friends and parties together
def test_the_dm_invites_a_friend_from_the_list(logged_in_page: Page, mira_page: Page, user: dict, mira: dict):
    befriend(logged_in_page, mira_page, mira["id"], user["id"])
    party = post(logged_in_page, "/api/parties", {"name": unique("The Lantern Bearers")})["party"]
    logged_in_page.goto(f"/dm/campaigns/parties/{party['id']}")
    logged_in_page.get_by_label("Or invite one of your friends").select_option(label=mira["name"])
    logged_in_page.get_by_role("button", name="Invite friend").click()
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text(f"{mira['name']} was invited to {party['name']}.")
    expect(PartiesPage(logged_in_page).invited).to_contain_text(mira["name"])
    expect(logged_in_page.get_by_test_id("no-friends-to-invite")).to_be_visible()  # nobody left to invite

    expect(PartiesPage(mira_page).open_player().invitations.filter(has_text=party["name"])).to_have_count(1)


def test_a_player_suggests_a_friend_and_the_dm_invites_them(browser: Browser, browser_context_args: dict,
                                                            logged_in_page: Page, mira_page: Page,
                                                            create_user, user: dict, mira: dict):
    """Player-to-player invites need the DM's say-so: three people, three browsers."""
    tam = create_user(name=unique("Tam Ashdown"))
    tam_context, tam_page = browser_for(browser, browser_context_args, tam)
    party = post(logged_in_page, "/api/parties", {"name": unique("The Lantern Bearers")})["party"]
    post(logged_in_page, f"/api/parties/{party['id']}/invites", {"email": mira["email"]})
    post(mira_page, f"/api/parties/{party['id']}/accept")
    befriend(mira_page, tam_page, tam["id"], mira["id"])

    mira_page.goto(f"/play/campaigns/parties/{party['id']}")
    mira_page.get_by_label("Friend to suggest").select_option(label=tam["name"])
    mira_page.get_by_role("button", name="Suggest", exact=True).click()
    expect(mira_page.get_by_test_id("flash-success").last).to_have_text(f"You suggested {tam['name']}. {user['name']} will decide.")
    expect(mira_page.get_by_test_id("suggestion")).to_contain_text(f"Waiting for {user['name']}")

    expect(PartiesPage(tam_page).open_player().invitations).to_have_count(0)  # nothing until the DM decides

    requests = JoinRequestsPage(logged_in_page).open()
    expect(requests.request(tam["name"])).to_contain_text(f"{mira['name']} suggested their friend {tam['name']}")
    requests.request(tam["name"]).get_by_role("button", name=f"Accept {tam['name']}").click()
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text(f"{tam['name']} was invited to {party['name']}.")

    tam_parties = PartiesPage(tam_page).open_player()
    expect(tam_parties.invitations.filter(has_text=party["name"])).to_have_count(1)
    tam_page.get_by_role("button", name=f"Accept the invitation to {party['name']}").click()
    expect(tam_parties.party_cards.filter(has_text=party["name"])).to_have_count(1)

    mira_page.reload()
    expect(mira_page.get_by_test_id("party-roster")).to_contain_text(tam["name"])
    expect(mira_page.get_by_test_id("suggestion")).to_have_count(0)
    tam_context.close()


def test_withdraw_a_suggestion(browser: Browser, browser_context_args: dict, logged_in_page: Page,
                               mira_page: Page, create_user, mira: dict):
    tam = create_user(name=unique("Tam Ashdown"))
    tam_context, tam_page = browser_for(browser, browser_context_args, tam)
    party = post(logged_in_page, "/api/parties", {"name": unique("The Lantern Bearers")})["party"]
    post(logged_in_page, f"/api/parties/{party['id']}/invites", {"email": mira["email"]})
    post(mira_page, f"/api/parties/{party['id']}/accept")
    befriend(mira_page, tam_page, tam["id"], mira["id"])
    post(mira_page, f"/api/parties/{party['id']}/requests", {"user_id": tam["id"]})

    mira_page.goto(f"/play/campaigns/parties/{party['id']}")
    mira_page.get_by_role("button", name=f"Withdraw your suggestion of {tam['name']}").click()
    expect(mira_page.get_by_test_id("flash-info").last).to_have_text(f"You withdrew your suggestion of {tam['name']}.")
    expect(mira_page.get_by_test_id("suggestion")).to_have_count(0)
    expect(mira_page.get_by_label("Friend to suggest").locator("option", has_text=tam["name"])).to_have_count(1)
    expect(JoinRequestsPage(logged_in_page).open().empty).to_be_visible()
    tam_context.close()
