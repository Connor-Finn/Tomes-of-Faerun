"""Friends, people search and joining parties, through the API (/api/people, /api/friends, /api/parties/...).

Fast, browser-less checks of the rules the pages rely on: who can find whom, who can ask to join which
party, and that the Dungeon Master always has the final say.
"""
from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import APIRequestContext, Playwright

from conftest import API_HEADERS

pytestmark = pytest.mark.api


def login(playwright: Playwright, base_url: str, someone: dict) -> APIRequestContext:
    ctx = playwright.request.new_context(base_url=base_url, extra_http_headers=API_HEADERS)
    assert ctx.post("/api/auth/login", data={"email": someone["email"], "password": someone["password"]}).ok
    return ctx


def unique(name: str) -> str:
    """A name nobody else in the test database has, so searches find exactly one person."""
    return f"{name} {uuid.uuid4().hex[:6]}"


@pytest.fixture
def someone(playwright: Playwright, base_url: str, create_user):
    """Factory: someone(name) -> (user dict, logged-in API client)."""
    clients = []

    def _make(name: str = "Mira Thorn"):
        person = create_user(name=unique(name))
        ctx = login(playwright, base_url, person)
        clients.append(ctx)
        return person, ctx
    yield _make
    for ctx in clients:
        ctx.dispose()


def befriend(a: APIRequestContext, b: APIRequestContext, b_id: int, a_id: int) -> None:
    assert a.post("/api/friends", data={"user_id": b_id}).status == 201
    assert b.post(f"/api/friends/{a_id}/accept").ok


def party(dm: APIRequestContext, visibility: str = "public", name: str | None = None) -> dict:
    response = dm.post("/api/parties", data={"name": name or unique("The Lantern Bearers"), "visibility": visibility})
    assert response.status == 201, response.text()
    return response.json()["party"]


# ------------------------------------------------------------------ people search
def test_search_finds_people_by_name_without_their_email(someone, user_api: APIRequestContext, user: dict):
    mira, _ = someone("Mira Thorn")
    found = user_api.get("/api/people", params={"q": mira["name"][-10:]}).json()["people"]
    assert [p["name"] for p in found] == [mira["name"]]
    assert found[0]["relation"] is None
    assert "email" not in found[0]
    # Searching for an email finds nobody: emails stay private
    assert user_api.get("/api/people", params={"q": mira["email"]}).json()["people"] == []


def test_search_needs_two_letters_and_skips_you_banned_and_unverified(user_api: APIRequestContext, user: dict,
                                                                       create_user):
    assert user_api.get("/api/people", params={"q": "a"}).json() == {"people": [], "min_length": 2}
    me = user_api.get("/api/people", params={"q": user["name"]}).json()["people"]
    assert user["id"] not in [p["id"] for p in me]
    hidden = unique("Hidden")
    create_user(name=hidden, verified=False)
    assert user_api.get("/api/people", params={"q": hidden}).json()["people"] == []
    assert user_api.get("/api/people", params={"q": "Banned Bandit"}).json()["people"] == []


def test_search_treats_wildcards_as_plain_letters(user_api: APIRequestContext):
    assert user_api.get("/api/people", params={"q": "%%"}).json()["people"] == []


# ------------------------------------------------------------------ friend requests
def test_send_accept_and_unfriend(someone):
    mira, mira_api = someone("Mira")
    tam, tam_api = someone("Tam")
    sent = mira_api.post("/api/friends", data={"user_id": tam["id"]})
    assert sent.status == 201 and sent.json()["relation"] == "sent"

    assert mira_api.get("/api/friends").json()["sent"][0]["name"] == tam["name"]
    received = tam_api.get("/api/friends").json()["received"]
    assert [r["name"] for r in received] == [mira["name"]]
    assert tam_api.get("/api/people", params={"q": mira["name"]}).json()["people"][0]["relation"] == "received"

    assert tam_api.post(f"/api/friends/{mira['id']}/accept").json()["message"] == f"You and {mira['name']} are now friends."
    assert [f["name"] for f in mira_api.get("/api/friends").json()["friends"]] == [tam["name"]]
    assert mira_api.get("/api/people", params={"q": tam["name"]}).json()["people"][0]["relation"] == "friend"

    assert mira_api.delete(f"/api/friends/{tam['id']}").json()["message"] == f"You and {tam['name']} are no longer friends."
    assert tam_api.get("/api/friends").json()["friends"] == []


def test_asking_someone_who_already_asked_you_makes_you_friends(someone):
    mira, mira_api = someone("Mira")
    tam, tam_api = someone("Tam")
    mira_api.post("/api/friends", data={"user_id": tam["id"]})
    response = tam_api.post("/api/friends", data={"user_id": mira["id"]})
    assert response.ok and response.json()["relation"] == "friend"


def test_duplicate_requests_and_self_requests_are_refused(someone, user_api: APIRequestContext, user: dict):
    tam, _ = someone("Tam")
    assert user_api.post("/api/friends", data={"user_id": tam["id"]}).status == 201
    again = user_api.post("/api/friends", data={"user_id": tam["id"]})
    assert again.status == 400 and "already sent" in again.json()["error"]
    assert user_api.post("/api/friends", data={"user_id": user["id"]}).status == 404


def test_only_the_person_asked_can_accept(someone):
    mira, mira_api = someone("Mira")
    tam, _ = someone("Tam")
    mira_api.post("/api/friends", data={"user_id": tam["id"]})
    assert mira_api.post(f"/api/friends/{tam['id']}/accept").status == 404


def test_declining_and_cancelling(someone):
    mira, mira_api = someone("Mira")
    tam, tam_api = someone("Tam")
    mira_api.post("/api/friends", data={"user_id": tam["id"]})
    assert tam_api.delete(f"/api/friends/{mira['id']}").json()["message"] == f"You declined {mira['name']}'s friend request."
    mira_api.post("/api/friends", data={"user_id": tam["id"]})
    assert mira_api.delete(f"/api/friends/{tam['id']}").json()["message"] == f"Your friend request to {tam['name']} was cancelled."
    assert tam_api.get("/api/friends").json()["received"] == []


# ------------------------------------------------------------------ public parties and join requests
def test_public_parties_are_listed_and_private_ones_are_not(someone, user_api: APIRequestContext):
    public = party(user_api, "public")
    private = party(user_api, "private")
    _, mira_api = someone("Mira")
    listed = {p["id"]: p for p in mira_api.get("/api/parties/public").json()["parties"]}
    assert public["id"] in listed and private["id"] not in listed
    assert listed[public["id"]]["standing"] is None
    # The DM doesn't see their own parties in the search
    assert public["id"] not in [p["id"] for p in user_api.get("/api/parties/public").json()["parties"]]
    found = mira_api.get("/api/parties/public", params={"q": public["name"]}).json()["parties"]
    assert [p["id"] for p in found] == [public["id"]]


def test_ask_to_join_and_the_dm_says_yes(someone, user_api: APIRequestContext, user: dict):
    p = party(user_api)
    mira, mira_api = someone("Mira")
    asked = mira_api.post(f"/api/parties/{p['id']}/requests", data={"message": "I play a halfling bard."})
    assert asked.status == 201, asked.text()
    assert asked.json()["message"] == f"You asked to join {p['name']}. {user['name']} will decide."
    standing = next(x for x in mira_api.get("/api/parties/public").json()["parties"] if x["id"] == p["id"])
    assert standing["standing"] == "requested"

    waiting = user_api.get("/api/parties/requests").json()["requests"]
    assert [(r["person"]["name"], r["message"], r["suggested_by"]) for r in waiting] == \
        [(mira["name"], "I play a halfling bard.", None)]
    led = next(x for x in user_api.get("/api/parties").json()["led"] if x["id"] == p["id"])
    assert led["request_count"] == 1

    accepted = user_api.post(f"/api/parties/{p['id']}/requests/{waiting[0]['id']}/accept")
    assert accepted.json()["message"] == f"{mira['name']} joined {p['name']}."
    assert [m["status"] for m in accepted.json()["party"]["members"]] == ["member"]  # straight in, no invitation
    assert [x["id"] for x in mira_api.get("/api/parties").json()["joined"]] == [p["id"]]
    assert user_api.get("/api/parties/requests").json()["requests"] == []


def test_the_dm_can_say_no_and_a_player_can_withdraw(someone, user_api: APIRequestContext):
    p = party(user_api)
    mira, mira_api = someone("Mira")
    r = mira_api.post(f"/api/parties/{p['id']}/requests").json()["request"]
    assert user_api.delete(f"/api/parties/{p['id']}/requests/{r['id']}").json()["message"] == \
        f"You turned down {mira['name']}'s request."
    assert mira_api.get("/api/parties").json()["joined"] == []

    r = mira_api.post(f"/api/parties/{p['id']}/requests").json()["request"]
    assert mira_api.delete(f"/api/parties/{p['id']}/requests/{r['id']}").json()["message"] == \
        f"You withdrew your request to join {p['name']}."
    assert user_api.get("/api/parties/requests").json()["requests"] == []


def test_private_parties_and_repeat_requests_are_refused(someone, user_api: APIRequestContext):
    private = party(user_api, "private")
    _, mira_api = someone("Mira")
    assert mira_api.post(f"/api/parties/{private['id']}/requests").status == 404
    public = party(user_api)
    assert mira_api.post(f"/api/parties/{public['id']}/requests").status == 201
    again = mira_api.post(f"/api/parties/{public['id']}/requests")
    assert again.status == 400 and again.json()["error"] == "You've already asked to join."
    assert user_api.post(f"/api/parties/{public['id']}/requests").json()["error"] == "You lead this party already."


def test_a_long_note_is_refused(someone, user_api: APIRequestContext):
    p = party(user_api)
    _, mira_api = someone("Mira")
    response = mira_api.post(f"/api/parties/{p['id']}/requests", data={"message": "x" * 301})
    assert response.status == 400
    assert response.json()["errors"]["message"] == "Keep your note to 300 characters or fewer."


def test_strangers_cannot_answer_requests(someone, user_api: APIRequestContext, other_api: APIRequestContext):
    p = party(user_api)
    _, mira_api = someone("Mira")
    r = mira_api.post(f"/api/parties/{p['id']}/requests").json()["request"]
    assert other_api.post(f"/api/parties/{p['id']}/requests/{r['id']}/accept").status == 404
    assert other_api.delete(f"/api/parties/{p['id']}/requests/{r['id']}").status == 404
    assert other_api.get("/api/parties/requests").json()["requests"] == []


# ------------------------------------------------------------------ friends and parties together
def test_the_dm_invites_a_friend_without_their_email(someone, user_api: APIRequestContext, user: dict):
    tam, tam_api = someone("Tam")
    befriend(user_api, tam_api, tam["id"], user["id"])
    p = party(user_api, "private")
    detail = user_api.get(f"/api/parties/{p['id']}").json()["party"]
    assert [f["name"] for f in detail["friends"]] == [tam["name"]]
    invited = user_api.post(f"/api/parties/{p['id']}/invites", data={"user_id": tam["id"]})
    assert invited.status == 201, invited.text()
    assert invited.json()["party"]["friends"] == []  # invited friends drop off the list
    assert [x["id"] for x in tam_api.get("/api/parties").json()["invitations"]] == [p["id"]]


def test_the_dm_cannot_invite_a_stranger_by_id(someone, user_api: APIRequestContext):
    tam, _ = someone("Tam")
    p = party(user_api, "private")
    response = user_api.post(f"/api/parties/{p['id']}/invites", data={"user_id": tam["id"]})
    assert response.status == 400 and response.json()["errors"]["user_id"] == "Choose one of your friends."


def test_a_member_suggests_a_friend_and_the_dm_decides(someone, user_api: APIRequestContext, user: dict):
    """Player-to-player invites need the DM's permission: the friend gets an invitation only once the DM says yes."""
    mira, mira_api = someone("Mira")
    tam, tam_api = someone("Tam")
    p = party(user_api, "private")
    user_api.post(f"/api/parties/{p['id']}/invites", data={"email": mira["email"]})
    mira_api.post(f"/api/parties/{p['id']}/accept")
    befriend(mira_api, tam_api, tam["id"], mira["id"])

    suggested = mira_api.post(f"/api/parties/{p['id']}/requests", data={"user_id": tam["id"]})
    assert suggested.status == 201, suggested.text()
    assert suggested.json()["message"] == f"You suggested {tam['name']}. {user['name']} will decide."
    assert tam_api.get("/api/parties").json()["invitations"] == []  # nothing yet: the DM hasn't decided
    mine = mira_api.get(f"/api/parties/{p['id']}").json()["party"]
    assert [s["person"]["name"] for s in mine["suggestions"]] == [tam["name"]]
    assert mine["friends"] == []  # already suggested

    waiting = user_api.get("/api/parties/requests").json()["requests"]
    assert waiting[0]["suggested_by"]["name"] == mira["name"]
    accepted = user_api.post(f"/api/parties/{p['id']}/requests/{waiting[0]['id']}/accept")
    assert accepted.json()["message"] == f"{tam['name']} was invited to {p['name']}."
    assert [x["id"] for x in tam_api.get("/api/parties").json()["invitations"]] == [p["id"]]


def test_only_members_can_suggest_and_only_their_friends(someone, user_api: APIRequestContext):
    mira, mira_api = someone("Mira")
    tam, tam_api = someone("Tam")
    p = party(user_api, "private")
    befriend(mira_api, tam_api, tam["id"], mira["id"])
    assert mira_api.post(f"/api/parties/{p['id']}/requests", data={"user_id": tam["id"]}).status == 404  # not a member

    user_api.post(f"/api/parties/{p['id']}/invites", data={"email": mira["email"]})
    mira_api.post(f"/api/parties/{p['id']}/accept")
    stranger, _ = someone("Stranger")
    response = mira_api.post(f"/api/parties/{p['id']}/requests", data={"user_id": stranger["id"]})
    assert response.status == 400 and response.json()["errors"]["user_id"] == "Choose one of your friends."


def test_inviting_someone_clears_their_request(someone, user_api: APIRequestContext):
    p = party(user_api)
    mira, mira_api = someone("Mira")
    mira_api.post(f"/api/parties/{p['id']}/requests")
    user_api.post(f"/api/parties/{p['id']}/invites", data={"email": mira["email"]})
    assert user_api.get("/api/parties/requests").json()["requests"] == []
