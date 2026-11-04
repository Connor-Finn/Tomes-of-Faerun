"""Character Manager API: /api/characters.

The rules themselves are covered in test_character_rules.py. These tests cover what the API
adds on top: who can see and change a character, drafts versus finished characters, templates,
and that the server (not the browser) refuses illegal builds.
"""
import pytest
from playwright.sync_api import APIRequestContext

from builds import aldric, autofill, blank

pytestmark = pytest.mark.api


def api_check(ctx: APIRequestContext):
    def _check(build: dict) -> dict:
        response = ctx.post("/api/characters/check", data={"build": build})
        assert response.ok, response.text()
        return response.json()
    return _check


def create(ctx: APIRequestContext, **body) -> dict:
    response = ctx.post("/api/characters", data=body)
    assert response.status == 201, response.text()
    return response.json()


# ------------------------------------------------------------------ reference data
def test_options_list_the_first_choices(api: APIRequestContext):
    body = api.get("/api/characters/options").json()
    assert len(body["races"]) == 9
    assert len(body["classes"]) == 12
    fighter = next(c for c in body["classes"] if c["index"] == "fighter")
    assert fighter["hit_die"] == 10 and fighter["subclass_level"] == 3
    assert body["standard_array"] == [15, 14, 13, 12, 10, 8]
    assert body["point_buy"]["budget"] == 27
    assert body["easy_max_level"] == 3


def test_templates_include_the_human_fighter(api: APIRequestContext):
    templates = api.get("/api/characters/templates").json()["templates"]
    aldric_t = next(t for t in templates if t["id"] == "human-fighter")
    assert aldric_t["name"] == "Aldric Vane"
    assert aldric_t["class"] == "Fighter" and aldric_t["level"] == 1
    assert aldric_t["hit_points"] == 12 and aldric_t["armor_class"] == 18


# ------------------------------------------------------------------ access
@pytest.mark.parametrize("method,url", [
    ("get", "/api/characters"), ("post", "/api/characters"), ("post", "/api/characters/check"),
    ("get", "/api/characters/1"), ("patch", "/api/characters/1"), ("delete", "/api/characters/1"),
])
def test_characters_need_a_login(api: APIRequestContext, method: str, url: str):
    response = getattr(api, method)(url, **({} if method in ("get", "delete") else {"data": {}}))
    assert response.status == 401


def test_other_players_cant_see_or_change_your_character(user_api: APIRequestContext, other_api: APIRequestContext):
    character = create(user_api, template="human-fighter")["character"]
    url = f"/api/characters/{character['id']}"
    assert other_api.get(url).status == 404
    assert other_api.patch(url, data={"name": "Stolen"}).status == 404
    assert other_api.delete(url).status == 404
    assert other_api.get("/api/characters").json()["characters"] == []
    assert user_api.get(url).json()["character"]["name"] == "Aldric Vane"


# ------------------------------------------------------------------ creating
def test_create_from_a_template(user_api: APIRequestContext):
    body = create(user_api, template="human-fighter")
    character = body["character"]
    assert character["name"] == "Aldric Vane"
    assert character["status"] == "complete"
    assert character["template"] == "human-fighter"
    assert character["build_mode"] == "easy"
    assert body["sheet"]["hit_points"] == 12
    assert body["sheet"]["armor_class"] == 18


def test_unknown_template_is_404(user_api: APIRequestContext):
    assert user_api.post("/api/characters", data={"template": "dragon-king"}).status == 404


def test_an_unfinished_build_saves_as_a_draft(user_api: APIRequestContext):
    body = create(user_api, build={"name": "Half-written", "race": "elf"})
    assert body["character"]["status"] == "draft"
    assert body["complete"] is False
    assert {m["field"] for m in body["missing"]} >= {"class", "subrace", "background"}


def test_an_illegal_build_is_refused_with_reasons(user_api: APIRequestContext):
    build = aldric()
    build["choices"]["class:proficiency-0"] = ["skill-arcana", "skill-athletics"]   # Arcana isn't a fighter skill
    response = user_api.post("/api/characters", data={"build": build})
    assert response.status == 400
    body = response.json()
    assert body["error"] == "That build breaks the rules."
    assert any(e["field"] == "class:proficiency-0" for e in body["errors"])
    assert user_api.get("/api/characters").json()["characters"] == []


def test_a_finished_build_from_the_check_endpoint_saves_as_complete(user_api: APIRequestContext):
    build = autofill(api_check(user_api), blank(**{"class": "wizard", "race": "elf", "subrace": "high-elf", "level": 3,
                                                  "subclass": "evocation"}))
    body = create(user_api, build=build)
    assert body["character"]["status"] == "complete"
    assert body["sheet"]["spellcasting"]["slots"] == {"1": 4, "2": 2}


def test_easy_build_is_capped_at_level_3_when_creating(user_api: APIRequestContext):
    response = user_api.post("/api/characters", data={"build": blank(level=5), "build_mode": "easy"})
    assert response.status == 400
    assert "Easy build creates characters up to level 3" in response.json()["errors"][0]["message"]
    assert user_api.post("/api/characters", data={"build": blank(level=5), "build_mode": "standard"}).status == 201


def test_invalid_build_mode_is_refused(user_api: APIRequestContext):
    response = user_api.post("/api/characters", data={"build": blank(), "build_mode": "hard"})
    assert response.status == 400


def test_stale_choices_are_dropped_when_saving(user_api: APIRequestContext):
    build = aldric()
    build["class"] = "rogue"
    body = create(user_api, build=build)
    assert "feature:fighter-fighting-style" not in body["character"]["build"]["choices"]
    assert body["character"]["status"] == "draft"


# ------------------------------------------------------------------ changing
def test_rename_and_write_notes(user_api: APIRequestContext):
    character = create(user_api, template="human-fighter")["character"]
    url = f"/api/characters/{character['id']}"
    body = user_api.patch(url, data={"name": "Sir Aldric", "notes": {"backstory": "A new tale."}}).json()
    assert body["character"]["name"] == "Sir Aldric"
    assert body["sheet"]["notes"]["backstory"] == "A new tale."


def test_toggle_build_mode(user_api: APIRequestContext):
    character = create(user_api, build=blank(level=6), build_mode="standard")["character"]
    url = f"/api/characters/{character['id']}"
    # Switching a level 6 character to Easy build is fine: the cap only applies to creation
    assert user_api.patch(url, data={"build_mode": "easy"}).json()["character"]["build_mode"] == "easy"
    # ...but an Easy character can't be pushed past level 3 in the builder
    response = user_api.patch(url, data={"build": blank(level=7)})
    assert response.status == 400


def test_an_illegal_change_leaves_the_character_alone(user_api: APIRequestContext):
    character = create(user_api, template="human-fighter")["character"]
    url = f"/api/characters/{character['id']}"
    build = aldric()
    build["level"] = 25
    assert user_api.patch(url, data={"build": build}).status == 400
    assert user_api.get(url).json()["character"]["level"] == 1


def test_list_newest_first_then_delete(user_api: APIRequestContext):
    first = create(user_api, build=blank(name="First"))["character"]
    second = create(user_api, build=blank(name="Second"))["character"]
    names = [c["name"] for c in user_api.get("/api/characters").json()["characters"]]
    assert names[:2] == ["Second", "First"]
    response = user_api.delete(f"/api/characters/{first['id']}")
    assert response.ok
    remaining = [c["id"] for c in user_api.get("/api/characters").json()["characters"]]
    assert first["id"] not in remaining and second["id"] in remaining
    assert user_api.get(f"/api/characters/{first['id']}").status == 404

