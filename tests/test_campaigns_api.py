"""Campaigns and parties API: /api/campaigns and /api/parties.

The story these tests follow: a Dungeon Master makes a party and invites a player by email, the
player accepts, the DM attaches the party to a campaign, and the player brings a character. That
character becomes an *instance*: it levels up and takes damage in the campaign while the base
character in the Character Manager stays exactly as it was.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import APIRequestContext, Playwright

from builds import aldric, autofill, level_up
from conftest import API_HEADERS

pytestmark = pytest.mark.api


# ------------------------------------------------------------------ helpers
def login(playwright: Playwright, base_url: str, someone: dict) -> APIRequestContext:
    ctx = playwright.request.new_context(base_url=base_url, extra_http_headers=API_HEADERS)
    assert ctx.post("/api/auth/login", data={"email": someone["email"], "password": someone["password"]}).ok
    return ctx


@pytest.fixture
def player(create_user) -> dict:
    return create_user(name="Mira Thorn")


@pytest.fixture
def player_api(playwright: Playwright, base_url: str, player: dict) -> APIRequestContext:
    ctx = login(playwright, base_url, player)
    yield ctx
    ctx.dispose()


def new_campaign(ctx: APIRequestContext, name: str = "The Whispering Dead", **extra) -> dict:
    response = ctx.post("/api/campaigns", data={"name": name, **extra})
    assert response.status == 201, response.text()
    return response.json()["campaign"]


def new_party(ctx: APIRequestContext, name: str = "The Lantern Bearers", **extra) -> dict:
    response = ctx.post("/api/parties", data={"name": name, **extra})
    assert response.status == 201, response.text()
    return response.json()["party"]


def new_character(ctx: APIRequestContext, name: str = "Aldric Vane") -> dict:
    response = ctx.post("/api/characters", data={"build": {**aldric(), "name": name}})
    assert response.status == 201, response.text()
    return response.json()["character"]


@pytest.fixture
def table(user_api: APIRequestContext, player_api: APIRequestContext, player: dict) -> dict:
    """A campaign whose party has one player in it (user_api is the DM)."""
    party = new_party(user_api)
    assert user_api.post(f"/api/parties/{party['id']}/invites", data={"email": player["email"]}).status == 201
    assert player_api.post(f"/api/parties/{party['id']}/accept").ok
    campaign = new_campaign(user_api)
    assert user_api.patch(f"/api/campaigns/{campaign['id']}", data={"party_id": party["id"]}).ok
    return {"party": party, "campaign": campaign, "url": f"/api/campaigns/{campaign['id']}"}


# ------------------------------------------------------------------ access
@pytest.mark.parametrize("method,url", [
    ("get", "/api/campaigns"), ("post", "/api/campaigns"), ("get", "/api/campaigns/1"),
    ("patch", "/api/campaigns/1"), ("delete", "/api/campaigns/1"), ("post", "/api/campaigns/1/sessions"),
    ("put", "/api/campaigns/1/encounters/1"), ("post", "/api/campaigns/1/instance"),
    ("get", "/api/parties"), ("post", "/api/parties"), ("post", "/api/parties/1/invites"),
    ("post", "/api/parties/1/accept"),
])
def test_campaigns_and_parties_need_a_login(api: APIRequestContext, method: str, url: str):
    response = getattr(api, method)(url, **({} if method in ("get", "delete", "put") else {"data": {}}))
    assert response.status == 401


def test_strangers_cant_see_or_change_your_campaign(user_api: APIRequestContext, other_api: APIRequestContext):
    campaign = new_campaign(user_api)
    url = f"/api/campaigns/{campaign['id']}"
    assert other_api.get(url).status == 404
    assert other_api.patch(url, data={"name": "Mine now"}).status == 404
    assert other_api.delete(url).status == 404
    assert other_api.post(f"{url}/sessions", data={"played_on": "2026-11-01", "title": "x"}).status == 404
    assert other_api.get("/api/campaigns").json() == {"running": [], "playing": [], "limit": 30}


def test_strangers_cant_see_or_change_your_party(user_api: APIRequestContext, other_api: APIRequestContext):
    party = new_party(user_api)
    url = f"/api/parties/{party['id']}"
    assert other_api.get(url).status == 404
    assert other_api.patch(url, data={"name": "Ours"}).status == 404
    assert other_api.post(f"{url}/invites", data={"email": "x@example.com"}).status == 404
    assert other_api.post(f"{url}/accept").status == 404


# ------------------------------------------------------------------ campaigns
def test_create_a_campaign(user_api: APIRequestContext, user: dict):
    campaign = new_campaign(user_api, description="Undead stir beneath Neverwinter.")
    assert campaign["name"] == "The Whispering Dead"
    assert campaign["status"] == "planning" and campaign["status_label"] == "Planning"
    assert campaign["role"] == "dm"
    assert campaign["dm"]["name"] == user["name"]
    assert campaign["party"] is None and campaign["players"] == []
    assert campaign["sessions"] == [] and campaign["encounters"] == [] and campaign["dm_notes"] == ""
    running = user_api.get("/api/campaigns").json()["running"]
    assert [c["name"] for c in running] == ["The Whispering Dead"]


@pytest.mark.parametrize("data,field,message", [
    ({"name": ""}, "name", "Give the campaign a name."),
    ({"name": "x" * 81}, "name", "Keep the name to 80 characters or fewer."),
    ({"name": "Fine", "status": "paused"}, "status", "Status must be Planning, Active or Finished."),
    ({"name": "Fine", "description": "x" * 4001}, "description", "Keep the description to 4000 characters or fewer."),
])
def test_campaign_fields_are_checked(user_api: APIRequestContext, data: dict, field: str, message: str):
    response = user_api.post("/api/campaigns", data=data)
    assert response.status == 400
    assert response.json()["errors"][field] == message


def test_campaign_names_are_unique_per_dm(user_api: APIRequestContext, other_api: APIRequestContext):
    new_campaign(user_api)
    response = user_api.post("/api/campaigns", data={"name": "the whispering dead"})
    assert response.json()["errors"]["name"] == "You already run a campaign with that name."
    new_campaign(other_api)  # another DM can use the same name


def test_edit_overview_status_and_dm_notes(user_api: APIRequestContext):
    campaign = new_campaign(user_api)
    response = user_api.patch(f"/api/campaigns/{campaign['id']}", data={
        "name": "Save the Princess", "status": "active", "dm_notes": "The princess is the villain."})
    assert response.ok, response.text()
    body = response.json()["campaign"]
    assert (body["name"], body["status_label"], body["dm_notes"]) == ("Save the Princess", "Active",
                                                                       "The princess is the villain.")


def test_delete_a_campaign(user_api: APIRequestContext):
    campaign = new_campaign(user_api)
    response = user_api.delete(f"/api/campaigns/{campaign['id']}")
    assert response.json()["message"] == "The Whispering Dead was deleted."
    assert user_api.get(f"/api/campaigns/{campaign['id']}").status == 404


# ------------------------------------------------------------------ session log
def test_the_session_log_is_newest_first(user_api: APIRequestContext):
    url = f"/api/campaigns/{new_campaign(user_api)['id']}"
    user_api.post(f"{url}/sessions", data={"played_on": "2026-10-01", "title": "The crypt door"})
    response = user_api.post(f"{url}/sessions", data={"played_on": "2026-10-08", "title": "Bones in the dark",
                                                       "summary": "Two skeletons and a lich's diary."})
    assert response.status == 201
    body = response.json()["campaign"]
    assert [s["title"] for s in body["sessions"]] == ["Bones in the dark", "The crypt door"]
    assert body["last_played"] == "2026-10-08" and body["session_count"] == 2

    first = body["sessions"][1]["id"]
    edited = user_api.patch(f"{url}/sessions/{first}", data={"played_on": "2026-10-15"}).json()["campaign"]
    assert [s["title"] for s in edited["sessions"]] == ["The crypt door", "Bones in the dark"]
    after = user_api.delete(f"{url}/sessions/{first}").json()["campaign"]
    assert [s["title"] for s in after["sessions"]] == ["Bones in the dark"]


def test_a_session_needs_a_date_and_title(user_api: APIRequestContext):
    url = f"/api/campaigns/{new_campaign(user_api)['id']}/sessions"
    errors = user_api.post(url, data={"played_on": "someday", "title": ""}).json()["errors"]
    assert errors == {"played_on": "Pick the date the session was played.", "title": "Give the session a title."}


# ------------------------------------------------------------------ encounters
def test_attach_a_bestiary_collection_as_an_encounter(user_api: APIRequestContext):
    campaign = new_campaign(user_api)
    collection = user_api.post("/api/bestiary/collections", data={"name": "Warlock boss dungeon"}).json()["collection"]
    user_api.post(f"/api/bestiary/collections/{collection['id']}/monsters", data={"monster": "goblin", "count": 4})
    url = f"/api/campaigns/{campaign['id']}/encounters/{collection['id']}"

    response = user_api.put(url)
    assert response.status == 201
    assert response.json()["message"] == "Warlock boss dungeon was added to The Whispering Dead's encounters."
    encounters = response.json()["campaign"]["encounters"]
    assert encounters[0]["collection"]["name"] == "Warlock boss dungeon"
    assert encounters[0]["collection"]["monster_count"] == 4 and encounters[0]["collection"]["total_xp"] == 200
    assert user_api.put(url).status == 200  # attaching twice changes nothing
    assert len(user_api.get(f"/api/campaigns/{campaign['id']}").json()["campaign"]["encounters"]) == 1

    assert user_api.delete(url).ok
    assert user_api.get(f"/api/campaigns/{campaign['id']}").json()["campaign"]["encounters"] == []
    assert user_api.get(f"/api/bestiary/collections/{collection['id']}").ok  # the collection itself is kept


def test_deleting_a_collection_takes_it_off_the_campaign(user_api: APIRequestContext):
    campaign = new_campaign(user_api)
    collection = user_api.post("/api/bestiary/collections", data={"name": "Goblin ambush"}).json()["collection"]
    user_api.put(f"/api/campaigns/{campaign['id']}/encounters/{collection['id']}")
    user_api.delete(f"/api/bestiary/collections/{collection['id']}")
    assert user_api.get(f"/api/campaigns/{campaign['id']}").json()["campaign"]["encounters"] == []


def test_you_cant_attach_someone_elses_collection(user_api: APIRequestContext, other_api: APIRequestContext):
    campaign = new_campaign(user_api)
    theirs = other_api.post("/api/bestiary/collections", data={"name": "Not yours"}).json()["collection"]
    assert user_api.put(f"/api/campaigns/{campaign['id']}/encounters/{theirs['id']}").status == 404


# ------------------------------------------------------------------ parties
def test_invite_accept_and_see_the_party(user_api, player_api, player, user):
    party = new_party(user_api, description="Lights in the dark.")
    response = user_api.post(f"/api/parties/{party['id']}/invites", data={"email": player["email"].upper()})
    assert response.status == 201
    assert response.json()["message"] == "Mira Thorn was invited to The Lantern Bearers."
    assert [(m["name"], m["status"]) for m in response.json()["party"]["members"]] == [("Mira Thorn", "invited")]

    invitations = player_api.get("/api/parties").json()["invitations"]
    assert [(i["name"], i["dm"]["name"]) for i in invitations] == [("The Lantern Bearers", user["name"])]

    joined = player_api.post(f"/api/parties/{party['id']}/accept").json()
    assert joined["message"] == "You joined The Lantern Bearers."
    assert joined["party"]["role"] == "player"
    assert "email" not in joined["party"]["members"][0]  # players never see each other's emails
    lists = player_api.get("/api/parties").json()
    assert lists["invitations"] == [] and [p["name"] for p in lists["joined"]] == ["The Lantern Bearers"]


@pytest.mark.parametrize("email,message", [
    ("", "Type the email address the player signed up with."),
    ("nobody_here@example.com", "No adventurer has signed up with that email."),
    ("unverified@example.com", "No adventurer has signed up with that email."),
])
def test_invites_need_a_real_player(user_api: APIRequestContext, email: str, message: str):
    party = new_party(user_api)
    response = user_api.post(f"/api/parties/{party['id']}/invites", data={"email": email})
    assert response.status == 400 and response.json()["errors"]["email"] == message


def test_you_cant_invite_yourself_or_invite_twice(user_api, player, user):
    party = new_party(user_api)
    url = f"/api/parties/{party['id']}/invites"
    assert user_api.post(url, data={"email": user["email"]}).json()["errors"]["email"] == \
        "You're the party's Dungeon Master, so you don't need an invitation."
    user_api.post(url, data={"email": player["email"]})
    assert user_api.post(url, data={"email": player["email"]}).json()["errors"]["email"] == \
        "Mira Thorn has already been invited."


def test_decline_an_invitation(user_api, player_api, player):
    party = new_party(user_api)
    user_api.post(f"/api/parties/{party['id']}/invites", data={"email": player["email"]})
    assert player_api.post(f"/api/parties/{party['id']}/decline").json()["message"] == \
        "You declined the invitation to The Lantern Bearers."
    assert player_api.get("/api/parties").json()["invitations"] == []
    assert user_api.get(f"/api/parties/{party['id']}").json()["party"]["members"] == []


def test_only_the_dm_manages_the_party(table, player_api, player):
    party_url = f"/api/parties/{table['party']['id']}"
    assert player_api.patch(party_url, data={"name": "Mira's crew"}).status == 403
    assert player_api.post(f"{party_url}/invites", data={"email": "admin@example.com"}).status == 403
    assert player_api.delete(party_url).status == 403
    # ...but a player can always leave
    assert player_api.delete(f"{party_url}/members/{player['id']}").json()["message"] == "You left The Lantern Bearers."
    assert player_api.get(table["url"]).status == 404


def test_disbanding_a_party_keeps_its_campaigns(table, user_api):
    assert user_api.delete(f"/api/parties/{table['party']['id']}").ok
    campaign = user_api.get(table["url"]).json()["campaign"]
    assert campaign["party"] is None and campaign["players"] == []


def test_you_can_only_attach_a_party_you_lead(user_api, other_api):
    campaign = new_campaign(user_api)
    theirs = new_party(other_api)
    response = user_api.patch(f"/api/campaigns/{campaign['id']}", data={"party_id": theirs["id"]})
    assert response.json()["errors"]["party_id"] == "Choose one of the parties you lead."


# ------------------------------------------------------------------ what players see
def test_players_see_the_overview_and_log_but_not_the_dms_pages(table, user_api, player_api):
    user_api.post(f"{table['url']}/sessions", data={"played_on": "2026-10-01", "title": "The crypt door"})
    user_api.patch(table["url"], data={"dm_notes": "Secret: the lich is their mentor."})
    body = player_api.get(table["url"]).json()["campaign"]
    assert body["role"] == "player"
    assert [s["title"] for s in body["sessions"]] == ["The crypt door"]
    assert "dm_notes" not in body and "encounters" not in body
    playing = player_api.get("/api/campaigns").json()["playing"]
    assert [c["name"] for c in playing] == ["The Whispering Dead"]


@pytest.mark.parametrize("method,suffix,data", [
    ("patch", "", {"name": "Hijacked"}), ("delete", "", None),
    ("post", "/sessions", {"played_on": "2026-10-01", "title": "Fake"}),
    ("put", "/encounters/1", None),
])
def test_players_cant_change_the_campaign(table, player_api, method, suffix, data):
    response = getattr(player_api, method)(table["url"] + suffix, **({"data": data} if data else {}))
    assert response.status == 403
    assert response.json()["error"] == "Only the campaign's Dungeon Master can do that."


# ------------------------------------------------------------------ character instances
def test_bring_a_character_and_it_becomes_an_instance(table, player_api):
    character = new_character(player_api)
    response = player_api.post(f"{table['url']}/instance", data={"character_id": character["id"]})
    assert response.status == 201, response.text()
    body = response.json()
    assert body["message"] == "Aldric Vane joined The Whispering Dead."
    instance = body["instance"]
    assert (instance["name"], instance["level"], instance["class"]) == ("Aldric Vane", 1, "Fighter")
    assert instance["current_hp"] == instance["max_hp"] == body["sheet"]["hit_points"]
    assert instance["base_character"]["id"] == character["id"]

    assert player_api.post(f"{table['url']}/instance", data={"character_id": character["id"]}).status == 409
    campaigns = player_api.get(f"/api/campaigns/characters/{character['id']}").json()["campaigns"]
    assert [(c["campaign"]["name"], c["instance"]["level"]) for c in campaigns] == [("The Whispering Dead", 1)]


def test_only_party_members_bring_characters(user_api, other_api):
    campaign = new_campaign(user_api)
    character = new_character(user_api)
    # the DM runs the campaign; they don't play in it
    assert user_api.post(f"/api/campaigns/{campaign['id']}/instance",
                         data={"character_id": character["id"]}).status == 403
    assert other_api.post(f"/api/campaigns/{campaign['id']}/instance", data={"character_id": 1}).status == 404


def test_drafts_and_other_peoples_characters_cant_join(table, player_api, user_api):
    draft = player_api.post("/api/characters", data={"build": {"name": "Half done", "level": 1}}).json()["character"]
    errors = player_api.post(f"{table['url']}/instance", data={"character_id": draft["id"]}).json()["errors"]
    assert errors["character_id"] == "Half done is still a draft. Finish it in the Character Manager first."
    dms = new_character(user_api, "DM's hero")
    errors = player_api.post(f"{table['url']}/instance", data={"character_id": dms["id"]}).json()["errors"]
    assert errors["character_id"] == "Choose one of your characters."


def test_track_hit_points(table, player_api):
    character = new_character(player_api)
    max_hp = player_api.post(f"{table['url']}/instance", data={"character_id": character["id"]}).json()["sheet"]["hit_points"]
    body = player_api.patch(f"{table['url']}/instance", data={"current_hp": 3, "temp_hp": 5}).json()["instance"]
    assert (body["current_hp"], body["temp_hp"], body["max_hp"]) == (3, 5, max_hp)
    too_many = player_api.patch(f"{table['url']}/instance", data={"current_hp": max_hp + 1})
    assert too_many.status == 400
    assert too_many.json()["error"] == f"Hit points must be a whole number from 0 to {max_hp}."


def test_levelling_up_the_instance_leaves_the_base_character_alone(table, player_api):
    character = new_character(player_api)
    player_api.post(f"{table['url']}/instance", data={"character_id": character["id"]})
    body = level_up(player_api, table["url"], 3)
    assert body["instance"]["level"] == 3
    assert body["sheet"]["summary"]["subclass"] == "Champion"
    assert player_api.get(f"/api/characters/{character['id']}").json()["character"]["level"] == 1


def test_a_level_up_needs_every_new_pick(table, player_api):
    character = new_character(player_api)
    player_api.post(f"{table['url']}/instance", data={"character_id": character["id"]})
    level_up(player_api, table["url"], 2)
    preview = player_api.get(f"{table['url']}/instance/level-up").json()["level_up"]
    assert preview["subclass_unlocks"] is True
    response = player_api.post(f"{table['url']}/instance/level-up", data={"build": preview["build"], "hp_method": "average"})
    assert response.status == 400
    assert response.json()["error"] == "Make every choice for level 3 first."


def test_easy_build_instances_can_level_past_three(table, player_api):
    character = player_api.post("/api/characters", data={"build": aldric(), "build_mode": "easy"}).json()["character"]
    player_api.post(f"{table['url']}/instance", data={"character_id": character["id"]})
    body = level_up(player_api, table["url"], 4)
    assert body["instance"]["level"] == 4 and body["instance"]["build_mode"] == "easy"


def test_the_dm_reads_the_sheet_and_sends_notes(table, user_api, player_api):
    character = new_character(player_api)
    instance = player_api.post(f"{table['url']}/instance", data={"character_id": character["id"]}).json()["instance"]
    url = f"{table['url']}/instances/{instance['id']}"

    sheet = user_api.get(url).json()
    assert sheet["instance"]["name"] == "Aldric Vane" and sheet["sheet"]["armor_class"] > 0
    players = user_api.get(table["url"]).json()["campaign"]["players"]
    assert players[0]["name"] == "Mira Thorn" and players[0]["instance"]["id"] == instance["id"]

    response = user_api.post(f"{url}/notes", data={"body": "You owe the Zhentarim 50 gold."})
    assert response.status == 201 and response.json()["message"] == "Your note was sent to Mira Thorn."
    user_api.post(f"{url}/notes", data={"body": "The ghoul's bite is festering."})
    notes = player_api.get(f"{table['url']}/instance").json()["instance"]["notes"]
    assert [n["body"] for n in notes] == ["The ghoul's bite is festering.", "You owe the Zhentarim 50 gold."]
    assert user_api.get(table["url"]).json()["campaign"]["players"][0]["instance"]["latest_note"]["body"] == \
        "The ghoul's bite is festering."
    deleted = user_api.delete(f"{url}/notes/{notes[1]['id']}")
    assert deleted.ok and len(deleted.json()["instance"]["notes"]) == 1
    assert user_api.post(f"{url}/notes", data={"body": "  "}).status == 400
    # the DM can read, but not change, the character
    assert user_api.patch(f"{table['url']}/instance", data={"current_hp": 0}).status == 403
    # and players can't write DM notes
    assert player_api.post(f"{url}/notes", data={"body": "I'm great"}).status == 403


def test_other_players_see_who_is_playing_but_not_their_sheets(table, user_api, player_api, create_user,
                                                               playwright, base_url):
    second = create_user(name="Bram Holt")
    user_api.post(f"/api/parties/{table['party']['id']}/invites", data={"email": second["email"]})
    bram = login(playwright, base_url, second)
    bram.post(f"/api/parties/{table['party']['id']}/accept")
    mira_char = new_character(player_api)
    mira = player_api.post(f"{table['url']}/instance", data={"character_id": mira_char["id"]}).json()["instance"]

    players = {p["name"]: p for p in bram.get(table["url"]).json()["campaign"]["players"]}
    assert players["Mira Thorn"]["instance"] == {"id": mira["id"], "name": "Aldric Vane", "level": 1, "class": "Fighter"}
    assert bram.get(f"{table['url']}/instances/{mira['id']}").status == 403
    bram.dispose()


def test_leave_the_campaign_with_a_character(table, player_api):
    character = new_character(player_api)
    player_api.post(f"{table['url']}/instance", data={"character_id": character["id"]})
    response = player_api.delete(f"{table['url']}/instance")
    assert response.json()["message"] == \
        "Aldric Vane left The Whispering Dead. Your character in the Character Manager is unchanged."
    assert player_api.get(f"{table['url']}/instance").status == 404
    assert player_api.get(f"/api/characters/{character['id']}").ok


def test_deleting_the_base_character_keeps_the_instance(table, player_api):
    character = new_character(player_api)
    player_api.post(f"{table['url']}/instance", data={"character_id": character["id"]})
    player_api.delete(f"/api/characters/{character['id']}")
    instance = player_api.get(f"{table['url']}/instance").json()["instance"]
    assert instance["name"] == "Aldric Vane" and instance["base_character"] is None
