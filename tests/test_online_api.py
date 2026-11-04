"""Online features API: published characters (/api/published) and party chat (/api/parties/<id>/messages).

Fast, browser-less checks of the rules the UI relies on: who may publish, copy, read, write and
strike out.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import APIRequestContext, Playwright

from builds import aldric, blank
from conftest import API_HEADERS

pytestmark = pytest.mark.api


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


def character(ctx: APIRequestContext, **build) -> dict:
    response = ctx.post("/api/characters", data={"build": {**aldric(), **build}})
    assert response.status == 201, response.text()
    return response.json()["character"]


# ------------------------------------------------------------------ published characters
def test_publish_copy_and_unpublish(user_api: APIRequestContext, other_api: APIRequestContext):
    mine = character(user_api, name="Sir Corwin")
    response = user_api.post("/api/published", data={"character_id": mine["id"], "summary": "A wall of steel."})
    assert response.status == 201, response.text()
    published = response.json()["published"]
    assert published["mine"] is True and published["copies"] == 0
    assert published["class"] == "Fighter" and published["hit_points"] > 0

    copy = other_api.post("/api/characters", data={"published": published["id"]})
    assert copy.status == 201, copy.text()
    assert copy.json()["character"]["name"] == "Sir Corwin"
    assert copy.json()["character"]["template"] == f"published-{published['id']}"

    seen = other_api.get("/api/published").json()["published"]
    entry = next(p for p in seen if p["id"] == published["id"])
    assert entry["mine"] is False and entry["copies"] == 1
    assert entry["character_id"] is None  # nobody else learns which of your characters it came from
    assert "email" not in entry["author"]

    assert other_api.delete(f"/api/published/{published['id']}").status == 404  # not theirs
    assert user_api.delete(f"/api/published/{published['id']}").ok
    assert other_api.post("/api/characters", data={"published": published["id"]}).status == 404
    assert other_api.get(f"/api/characters/{copy.json()['character']['id']}").ok  # the copy is kept


def test_only_your_own_finished_characters_can_be_published(user_api: APIRequestContext, other_api: APIRequestContext):
    theirs = character(other_api)
    response = user_api.post("/api/published", data={"character_id": theirs["id"]})
    assert response.status == 400
    assert response.json()["errors"]["character_id"] == "Choose one of your characters to publish."

    draft = user_api.post("/api/characters", data={"build": blank(name="Half-written")}).json()["character"]
    response = user_api.post("/api/published", data={"character_id": draft["id"]})
    assert response.status == 400
    assert "still a draft" in response.json()["error"]


def test_published_summary_has_a_length_limit(user_api: APIRequestContext):
    mine = character(user_api)
    response = user_api.post("/api/published", data={"character_id": mine["id"], "summary": "x" * 301})
    assert response.status == 400
    assert response.json()["errors"]["summary"] == "Keep the description to 300 characters or fewer."


def test_publishing_needs_a_login(api: APIRequestContext):
    assert api.get("/api/published").status == 401
    assert api.post("/api/published", data={"character_id": 1}).status == 401


# ------------------------------------------------------------------ party chat
@pytest.fixture
def party(user_api: APIRequestContext, player_api: APIRequestContext, player: dict) -> dict:
    party = user_api.post("/api/parties", data={"name": "The Lantern Bearers"}).json()["party"]
    assert user_api.post(f"/api/parties/{party['id']}/invites", data={"email": player["email"]}).status == 201
    return party


def test_invited_players_cannot_read_the_chat_until_they_join(user_api, player_api, party):
    url = f"/api/parties/{party['id']}/messages"
    assert user_api.post(url, data={"body": "Welcome!"}).status == 201
    assert player_api.get(url).status == 404
    assert player_api.post(url, data={"body": "Hello?"}).status == 404

    assert player_api.post(f"/api/parties/{party['id']}/accept").ok
    page = player_api.get(url).json()
    assert [m["body"] for m in page["messages"]] == ["Welcome!"]
    assert page["messages"][0]["from_dm"] is True and page["messages"][0]["can_strike"] is False


def test_strangers_cannot_read_write_or_strike(user_api, other_api, party):
    url = f"/api/parties/{party['id']}/messages"
    message = user_api.post(url, data={"body": "Secret plans"}).json()["message"]
    assert other_api.get(url).status == 404
    assert other_api.post(url, data={"body": "Hi"}).status == 404
    assert other_api.delete(f"{url}/{message['id']}").status == 404
    assert other_api.post(f"/api/parties/{party['id']}/writing").status == 404


def test_players_strike_only_their_own_messages(user_api, player_api, party):
    url = f"/api/parties/{party['id']}/messages"
    assert player_api.post(f"/api/parties/{party['id']}/accept").ok
    dm_message = user_api.post(url, data={"body": "From the DM"}).json()["message"]
    mine = player_api.post(url, data={"body": "From Mira"}).json()["message"]

    response = player_api.delete(f"{url}/{dm_message['id']}")
    assert response.status == 403
    assert player_api.delete(f"{url}/{mine['id']}").ok
    assert user_api.delete(f"{url}/{dm_message['id']}").ok
    assert user_api.get(url).json()["messages"] == []


def test_message_validation(user_api, party):
    url = f"/api/parties/{party['id']}/messages"
    assert user_api.post(url, data={"body": "  "}).json()["errors"]["body"] == "Write something first."
    too_long = user_api.post(url, data={"body": "a" * 1001})
    assert too_long.status == 400
    assert too_long.json()["errors"]["body"] == "Keep a message to 1000 characters or fewer."
    assert user_api.post(url, data={"body": "  trimmed  "}).json()["message"]["body"] == "trimmed"


def test_unread_counts_and_reading(user_api, player_api, party):
    url = f"/api/parties/{party['id']}/messages"
    assert player_api.post(f"/api/parties/{party['id']}/accept").ok
    for body in ("One", "Two", "Three"):
        user_api.post(url, data={"body": body})

    joined = player_api.get("/api/parties").json()["joined"]
    assert next(p for p in joined if p["id"] == party["id"])["unread"] == 3
    led = user_api.get("/api/parties").json()["led"]
    assert next(p for p in led if p["id"] == party["id"])["unread"] == 0  # your own writing is never unread

    first_look = player_api.get(url).json()
    assert first_look["last_read_id"] == 0
    second_look = player_api.get(url).json()
    assert second_look["last_read_id"] == first_look["messages"][-1]["id"]
    joined = player_api.get("/api/parties").json()["joined"]
    assert next(p for p in joined if p["id"] == party["id"])["unread"] == 0


def test_writing_indicator(user_api, player_api, party):
    url = f"/api/parties/{party['id']}/messages"
    assert player_api.post(f"/api/parties/{party['id']}/accept").ok
    assert player_api.post(f"/api/parties/{party['id']}/writing").ok
    assert user_api.get(url).json()["writing"] == ["Mira Thorn"]
    assert player_api.get(url).json()["writing"] == []  # not shown to yourself
    player_api.post(url, data={"body": "Done"})
    assert user_api.get(url).json()["writing"] == []  # sending stops the indicator


def test_older_pages(user_api, party):
    url = f"/api/parties/{party['id']}/messages"
    ids = [user_api.post(url, data={"body": f"Entry {n}"}).json()["message"]["id"] for n in range(55)]
    latest = user_api.get(url).json()
    assert len(latest["messages"]) == 50 and latest["has_more"] is True
    assert latest["messages"][0]["id"] == ids[5]
    older = user_api.get(f"{url}?before={ids[5]}").json()
    assert [m["id"] for m in older["messages"]] == ids[:5]
    assert older["has_more"] is False


def test_disbanding_a_party_removes_its_chat(user_api, party):
    url = f"/api/parties/{party['id']}/messages"
    user_api.post(url, data={"body": "Farewell"})
    assert user_api.delete(f"/api/parties/{party['id']}").ok
    assert user_api.get(url).status == 404
