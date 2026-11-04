"""Level roadmaps, following them in a campaign, backup copies, and publishing with roadmaps.

The story: Mira plans her fighter's level-ups as a roadmap in the Character Manager. In a campaign
her character can follow that roadmap: switching onto it rewrites the levelling choices to the
roadmap's (items stay), and each level-up after that takes the roadmap's next level. Before a big
change she can keep one backup copy per campaign, and swap back to it.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import APIRequestContext, Playwright

from builds import aldric, autofill, blank
from conftest import API_HEADERS

pytestmark = pytest.mark.api


# ------------------------------------------------------------------ helpers
def login(playwright: Playwright, base_url: str, someone: dict) -> APIRequestContext:
    ctx = playwright.request.new_context(base_url=base_url, extra_http_headers=API_HEADERS)
    assert ctx.post("/api/auth/login", data={"email": someone["email"], "password": someone["password"]}).ok
    return ctx


def checker(ctx: APIRequestContext):
    def check(build: dict) -> dict:
        response = ctx.post("/api/characters/check", data={"build": build})
        assert response.ok, response.text()
        return response.json()
    return check


def new_character(ctx: APIRequestContext, build: dict | None = None, name: str = "Aldric Vane") -> dict:
    response = ctx.post("/api/characters", data={"build": {**(build or aldric()), "name": name}})
    assert response.status == 201, response.text()
    assert response.json()["character"]["status"] == "complete", response.json()["missing"]
    return response.json()["character"]


def new_roadmap(ctx: APIRequestContext, character_id: int, name: str = "Champion route") -> dict:
    response = ctx.post(f"/api/characters/{character_id}/roadmaps", data={"name": name})
    assert response.status == 201, response.text()
    return response.json()["roadmap"]


SUBCLASSES = {"fighter": (3, "champion"), "wizard": (2, "evocation")}   # (level picked, the SRD's one)


def with_subclass(build: dict) -> dict:
    """autofill makes every pick but the subclass, which is a field of its own: choose the SRD's one."""
    level, subclass = SUBCLASSES[build["class"]]
    if build.get("level", 1) >= level and not build.get("subclass"):
        return {**build, "subclass": subclass}
    return build


def plan(ctx: APIRequestContext, roadmap_id: int, level: int, prefer: dict | None = None) -> dict:
    """Plan one level the way a player would: open it, make every choice, save."""
    opened = ctx.get(f"/api/roadmaps/{roadmap_id}/levels/{level}")
    assert opened.ok, opened.text()
    build = autofill(checker(ctx), with_subclass(opened.json()["character"]["build"]), prefer)
    response = ctx.put(f"/api/roadmaps/{roadmap_id}/levels/{level}", data={"build": build})
    assert response.ok, response.text()
    return response.json()["roadmap"]


def plan_to(ctx: APIRequestContext, roadmap_id: int, start: int, end: int, prefer: dict | None = None) -> dict:
    roadmap = {}
    for level in range(start + 1, end + 1):
        roadmap = plan(ctx, roadmap_id, level, prefer)
    return roadmap


@pytest.fixture
def player(create_user) -> dict:
    return create_user(name="Mira Thorn")


@pytest.fixture
def player_api(playwright: Playwright, base_url: str, player: dict) -> APIRequestContext:
    ctx = login(playwright, base_url, player)
    yield ctx
    ctx.dispose()


@pytest.fixture
def table(user_api: APIRequestContext, player_api: APIRequestContext, player: dict) -> dict:
    """A campaign whose party has the player in it (user_api is the DM)."""
    party = user_api.post("/api/parties", data={"name": "The Lantern Bearers"}).json()["party"]
    assert user_api.post(f"/api/parties/{party['id']}/invites", data={"email": player["email"]}).status == 201
    assert player_api.post(f"/api/parties/{party['id']}/accept").ok
    campaign = user_api.post("/api/campaigns", data={"name": "The Whispering Dead"}).json()["campaign"]
    assert user_api.patch(f"/api/campaigns/{campaign['id']}", data={"party_id": party["id"]}).ok
    return {"campaign": campaign, "url": f"/api/campaigns/{campaign['id']}"}


def bring(ctx: APIRequestContext, table: dict, character: dict) -> dict:
    response = ctx.post(f"{table['url']}/instance", data={"character_id": character["id"]})
    assert response.status == 201, response.text()
    return response.json()["instance"]


def level_up_by_hand(ctx: APIRequestContext, table: dict, level: int, prefer: dict | None = None) -> dict:
    current = ctx.get(f"{table['url']}/instance").json()["instance"]["build"]
    build = autofill(checker(ctx), with_subclass({**current, "level": level}), prefer)
    response = ctx.patch(f"{table['url']}/instance", data={"build": build})
    assert response.ok, response.text()
    return response.json()


# ------------------------------------------------------------------ access
@pytest.mark.parametrize("method,url", [
    ("get", "/api/characters/1/roadmaps"), ("post", "/api/characters/1/roadmaps"), ("get", "/api/roadmaps/1"),
    ("patch", "/api/roadmaps/1"), ("delete", "/api/roadmaps/1"), ("get", "/api/roadmaps/1/levels/2"),
    ("put", "/api/roadmaps/1/levels/2"), ("put", "/api/campaigns/1/instance/roadmap"),
    ("put", "/api/campaigns/1/instance/backup"), ("post", "/api/campaigns/1/instance/backup/restore"),
])
def test_roadmaps_need_a_login(api: APIRequestContext, method: str, url: str):
    response = getattr(api, method)(url, **({} if method in ("get", "delete") else {"data": {}}))
    assert response.status == 401


def test_strangers_cant_see_or_change_your_roadmaps(user_api: APIRequestContext, other_api: APIRequestContext):
    character = new_character(user_api)
    roadmap = new_roadmap(user_api, character["id"])
    url = f"/api/roadmaps/{roadmap['id']}"
    assert other_api.get(f"/api/characters/{character['id']}/roadmaps").status == 404
    assert other_api.post(f"/api/characters/{character['id']}/roadmaps", data={"name": "Mine"}).status == 404
    assert other_api.get(url).status == 404
    assert other_api.patch(url, data={"name": "Mine now"}).status == 404
    assert other_api.get(f"{url}/levels/2").status == 404
    assert other_api.put(f"{url}/levels/2", data={"build": aldric()}).status == 404
    assert other_api.delete(url).status == 404


# ------------------------------------------------------------------ roadmaps
def test_start_a_roadmap_at_the_characters_level(user_api: APIRequestContext):
    character = new_character(user_api)
    roadmap = new_roadmap(user_api, character["id"])
    assert roadmap["name"] == "Champion route"
    assert (roadmap["start_level"], roadmap["end_level"]) == (1, 1)
    assert [lvl["level"] for lvl in roadmap["levels"]] == [1]
    assert roadmap["levels"][0]["start"] and roadmap["levels"][0]["fits"]
    listed = user_api.get(f"/api/characters/{character['id']}/roadmaps").json()
    assert [r["name"] for r in listed["roadmaps"]] == ["Champion route"]
    assert listed["can_start"] is True


def test_plan_level_by_level_up_to_three(user_api: APIRequestContext):
    character = new_character(user_api)
    roadmap = new_roadmap(user_api, character["id"])
    roadmap = plan_to(user_api, roadmap["id"], 1, 3)
    assert roadmap["end_level"] == 3
    level3 = roadmap["levels"][2]
    assert level3["subclass"] == "Champion"
    assert any(c["label"] == "Subclass" and c["added"] == ["Champion"] for c in level3["changes"])
    assert "Improved Critical" in level3["new_features"]
    assert roadmap["levels"][1]["hit_points"] > roadmap["levels"][0]["hit_points"]
    # The character itself never levels up: roadmaps are plans
    assert user_api.get(f"/api/characters/{character['id']}").json()["character"]["level"] == 1


def test_open_the_next_level_to_plan(user_api: APIRequestContext):
    character = new_character(user_api)
    roadmap = new_roadmap(user_api, character["id"])
    opened = user_api.get(f"/api/roadmaps/{roadmap['id']}/levels/2").json()
    assert opened["planned"] is False
    assert opened["character"]["build"]["level"] == 2
    assert opened["character"]["build"]["race"] == "human"   # everything else comes from the character
    assert user_api.get(f"/api/roadmaps/{roadmap['id']}/levels/3").status == 404   # one level at a time


@pytest.mark.parametrize("level,message", [
    (1, "Level 1 is where the roadmap starts"),
    (3, "Plan level 2 first."),
    (21, "Roadmaps go up to level 20."),
])
def test_only_the_next_level_can_be_planned(user_api: APIRequestContext, level: int, message: str):
    character = new_character(user_api)
    roadmap = new_roadmap(user_api, character["id"])
    response = user_api.put(f"/api/roadmaps/{roadmap['id']}/levels/{level}", data={"build": {**aldric(), "level": level}})
    assert response.status == 400
    assert message in response.json()["error"]


def test_an_unfinished_level_is_refused(user_api: APIRequestContext):
    character = new_character(user_api)
    roadmap = new_roadmap(user_api, character["id"])
    plan(user_api, roadmap["id"], 2)
    opened = user_api.get(f"/api/roadmaps/{roadmap['id']}/levels/3").json()   # level 3: choose a subclass
    build = {**opened["character"]["build"], "subclass": None}
    response = user_api.put(f"/api/roadmaps/{roadmap['id']}/levels/3", data={"build": build})
    assert response.status == 400
    assert response.json()["error"] == "Make every choice for level 3 before saving it to the roadmap."


def test_a_roadmap_cant_change_who_the_character_is(user_api: APIRequestContext):
    character = new_character(user_api)
    roadmap = new_roadmap(user_api, character["id"])
    opened = user_api.get(f"/api/roadmaps/{roadmap['id']}/levels/2").json()
    build = autofill(checker(user_api), opened["character"]["build"])
    build.update(race="dwarf", subrace="hill-dwarf", name="Someone Else")
    assert user_api.put(f"/api/roadmaps/{roadmap['id']}/levels/2", data={"build": build}).ok
    level2 = user_api.get(f"/api/roadmaps/{roadmap['id']}/levels/2").json()["character"]["build"]
    assert (level2["race"], level2["name"]) == ("human", "Aldric Vane")


def test_replanning_an_earlier_level_clears_the_later_ones(user_api: APIRequestContext):
    character = new_character(user_api)
    roadmap = new_roadmap(user_api, character["id"])
    plan_to(user_api, roadmap["id"], 1, 4)
    build = user_api.get(f"/api/roadmaps/{roadmap['id']}/levels/2").json()["character"]["build"]
    response = user_api.put(f"/api/roadmaps/{roadmap['id']}/levels/2", data={"build": build})
    assert response.ok
    assert response.json()["roadmap"]["end_level"] == 2
    assert "The 2 levels planned after it were cleared." in response.json()["message"]


def test_remove_the_top_levels(user_api: APIRequestContext):
    character = new_character(user_api)
    roadmap = new_roadmap(user_api, character["id"])
    plan_to(user_api, roadmap["id"], 1, 3)
    response = user_api.delete(f"/api/roadmaps/{roadmap['id']}/levels/3")
    assert response.ok and response.json()["roadmap"]["end_level"] == 2
    assert user_api.delete(f"/api/roadmaps/{roadmap['id']}/levels/1").status == 400


def test_rename_and_delete_a_roadmap(user_api: APIRequestContext):
    character = new_character(user_api)
    roadmap = new_roadmap(user_api, character["id"])
    renamed = user_api.patch(f"/api/roadmaps/{roadmap['id']}", data={"name": "Sword and board"})
    assert renamed.ok and renamed.json()["roadmap"]["name"] == "Sword and board"
    assert user_api.patch(f"/api/roadmaps/{roadmap['id']}", data={"name": ""}).status == 400
    assert user_api.delete(f"/api/roadmaps/{roadmap['id']}").ok
    assert user_api.get(f"/api/roadmaps/{roadmap['id']}").status == 404


@pytest.mark.parametrize("name,message", [("", "Give the roadmap a name."),
                                          ("x" * 61, "Keep the name to 60 characters or fewer.")])
def test_a_roadmap_needs_a_name(user_api: APIRequestContext, name: str, message: str):
    character = new_character(user_api)
    response = user_api.post(f"/api/characters/{character['id']}/roadmaps", data={"name": name})
    assert response.status == 400 and response.json()["error"] == message


def test_drafts_and_level_20_characters_cant_start_a_roadmap(user_api: APIRequestContext):
    draft = user_api.post("/api/characters", data={"build": blank(name="Half Done")}).json()["character"]
    response = user_api.post(f"/api/characters/{draft['id']}/roadmaps", data={"name": "Plan"})
    assert response.status == 400 and "still a draft" in response.json()["error"]
    top = new_character(user_api, autofill(checker(user_api), with_subclass(blank(level=20))), name="Legend")
    response = user_api.post(f"/api/characters/{top['id']}/roadmaps", data={"name": "Plan"})
    assert response.status == 400 and "nothing left to plan" in response.json()["error"]


def test_a_casters_roadmap_keeps_each_levels_spells(user_api: APIRequestContext):
    wizard = new_character(user_api, autofill(checker(user_api), blank(**{"class": "wizard"})), name="Elara")
    roadmap = new_roadmap(user_api, wizard["id"], "Evoker")
    roadmap = plan_to(user_api, roadmap["id"], 1, 3)
    level2 = roadmap["levels"][1]
    assert any(c.get("slot") == "spells:spellbook" and len(c["added"]) == 2 for c in level2["changes"])
    # Level 2 still opens with level 2's spellbook, not level 3's
    build2 = user_api.get(f"/api/roadmaps/{roadmap['id']}/levels/2").json()["character"]["build"]
    build3 = user_api.get(f"/api/roadmaps/{roadmap['id']}/levels/3").json()["character"]["build"]
    assert len(build2["choices"]["spells:spellbook"]) == len(build3["choices"]["spells:spellbook"]) - 2


# ------------------------------------------------------------------ following in a campaign
def test_follow_a_roadmap_and_level_up_with_it(table: dict, player_api: APIRequestContext):
    character = new_character(player_api)
    roadmap = new_roadmap(player_api, character["id"])
    plan_to(player_api, roadmap["id"], 1, 3)
    bring(player_api, table, character)

    detail = player_api.get(f"{table['url']}/instance").json()["instance"]
    assert detail["following"] is None and detail["backup"] is None
    assert [(r["name"], r["covers_level"]) for r in detail["roadmaps"]] == [("Champion route", True)]

    followed = player_api.put(f"{table['url']}/instance/roadmap", data={"roadmap_id": roadmap["id"]})
    assert followed.ok, followed.text()
    following = followed.json()["instance"]["following"]
    assert following["name"] == "Champion route" and following["next_level"] == 2

    for level in (2, 3):
        up = player_api.post(f"{table['url']}/instance/roadmap/level-up")
        assert up.ok, up.text()
        assert up.json()["instance"]["level"] == level
    instance = up.json()["instance"]
    assert instance["subclass"] == "Champion"
    assert instance["following"]["next_level"] is None
    # Past the end of the roadmap
    stuck = player_api.post(f"{table['url']}/instance/roadmap/level-up")
    assert stuck.status == 400 and "stops at level 3" in stuck.json()["error"]
    # The roadmap knows who follows it
    listed = player_api.get(f"/api/characters/{character['id']}/roadmaps").json()["roadmaps"][0]
    assert listed["followed_by"] == [{"campaign": {"id": table["campaign"]["id"], "name": "The Whispering Dead"}, "level": 3}]


def test_switching_onto_a_roadmap_rewrites_choices_and_keeps_items(table: dict, player_api: APIRequestContext):
    character = new_character(player_api)
    roadmap = new_roadmap(player_api, character["id"])
    plan_to(player_api, roadmap["id"], 1, 2, prefer={"feature:fighter-fighting-style": ["fighter-fighting-style-defense"]})
    bring(player_api, table, character)
    # Level up by hand first, with a different pick, and pick up a bag of holding
    current = player_api.get(f"{table['url']}/instance").json()["instance"]["build"]
    player_api.patch(f"{table['url']}/instance", data={"build": {**current, "items": {"bag-of-holding": 1}}})
    level_up_by_hand(player_api, table, 2)

    followed = player_api.put(f"{table['url']}/instance/roadmap", data={"roadmap_id": roadmap["id"]}).json()
    build = followed["instance"]["build"]
    planned = player_api.get(f"/api/roadmaps/{roadmap['id']}/levels/2").json()["character"]["build"]
    levelling = {k: v for k, v in planned["choices"].items() if not k.startswith("equipment:")}
    assert {k: v for k, v in build["choices"].items() if not k.startswith("equipment:")} == levelling
    assert build["items"] == {"bag-of-holding": 1}
    assert build["level"] == 2


def test_a_roadmap_that_doesnt_reach_the_instances_level_cant_be_followed(table: dict, player_api: APIRequestContext):
    character = new_character(player_api)
    roadmap = new_roadmap(player_api, character["id"])
    plan(player_api, roadmap["id"], 2)
    bring(player_api, table, character)
    level_up_by_hand(player_api, table, 3)
    response = player_api.put(f"{table['url']}/instance/roadmap", data={"roadmap_id": roadmap["id"]})
    assert response.status == 400
    assert response.json()["errors"]["roadmap_id"] == (
        "“Champion route” plans levels 1 to 2, but Aldric Vane is level 3 here. Plan up to level 3 first.")


def test_only_the_characters_own_roadmaps_can_be_followed(table: dict, player_api: APIRequestContext):
    character = new_character(player_api)
    other = new_character(player_api, name="Brother")
    roadmap = new_roadmap(player_api, other["id"])
    bring(player_api, table, character)
    response = player_api.put(f"{table['url']}/instance/roadmap", data={"roadmap_id": roadmap["id"]})
    assert response.status == 400
    assert response.json()["errors"]["roadmap_id"] == "Choose one of Aldric Vane's roadmaps."


def test_levelling_by_hand_stops_following(table: dict, player_api: APIRequestContext):
    character = new_character(player_api)
    roadmap = new_roadmap(player_api, character["id"])
    plan(player_api, roadmap["id"], 2)
    bring(player_api, table, character)
    player_api.put(f"{table['url']}/instance/roadmap", data={"roadmap_id": roadmap["id"]})
    result = level_up_by_hand(player_api, table, 2)
    assert result["instance"]["following"] is None
    assert result["message"] == "Aldric Vane stopped following the roadmap “Champion route”."
    # Hit points alone don't count as choosing by hand
    player_api.put(f"{table['url']}/instance/roadmap", data={"roadmap_id": roadmap["id"]})
    hp = player_api.patch(f"{table['url']}/instance", data={"current_hp": 3}).json()
    assert hp["instance"]["following"]["name"] == "Champion route"


def test_stop_following(table: dict, player_api: APIRequestContext):
    character = new_character(player_api)
    roadmap = new_roadmap(player_api, character["id"])
    bring(player_api, table, character)
    player_api.put(f"{table['url']}/instance/roadmap", data={"roadmap_id": roadmap["id"]})
    stopped = player_api.delete(f"{table['url']}/instance/roadmap")
    assert stopped.ok and stopped.json()["instance"]["following"] is None
    assert player_api.delete(f"{table['url']}/instance/roadmap").status == 400


def test_deleting_a_followed_roadmap_keeps_the_instance(table: dict, player_api: APIRequestContext):
    character = new_character(player_api)
    roadmap = new_roadmap(player_api, character["id"])
    plan(player_api, roadmap["id"], 2)
    bring(player_api, table, character)
    player_api.put(f"{table['url']}/instance/roadmap", data={"roadmap_id": roadmap["id"]})
    player_api.post(f"{table['url']}/instance/roadmap/level-up")
    deleted = player_api.delete(f"/api/roadmaps/{roadmap['id']}")
    assert "1 campaign character stopped following it" in deleted.json()["message"]
    instance = player_api.get(f"{table['url']}/instance").json()["instance"]
    assert instance["following"] is None and instance["level"] == 2


def test_the_dm_doesnt_see_roadmaps_or_backups(table: dict, user_api: APIRequestContext, player_api: APIRequestContext):
    character = new_character(player_api)
    instance = bring(player_api, table, character)
    seen = user_api.get(f"{table['url']}/instances/{instance['id']}").json()["instance"]
    assert "backup" not in seen and "roadmaps" not in seen


# ------------------------------------------------------------------ backups
def test_save_and_restore_a_backup(table: dict, player_api: APIRequestContext):
    character = new_character(player_api)
    bring(player_api, table, character)
    saved = player_api.put(f"{table['url']}/instance/backup", data={})
    assert saved.ok
    backup = saved.json()["instance"]["backup"]
    assert backup["level"] == 1 and backup["reason"] == "Saved by hand"

    level_up_by_hand(player_api, table, 2)
    restored = player_api.post(f"{table['url']}/instance/backup/restore")
    assert restored.ok
    body = restored.json()
    assert body["instance"]["level"] == 1
    # The level 2 character was swapped into the backup, so nothing is lost
    assert body["instance"]["backup"]["level"] == 2
    assert "The character you swapped out is now the backup." in body["message"]


def test_one_backup_per_campaign_and_overwriting_needs_a_yes(table: dict, player_api: APIRequestContext):
    character = new_character(player_api)
    bring(player_api, table, character)
    player_api.put(f"{table['url']}/instance/backup", data={})
    level_up_by_hand(player_api, table, 2)
    again = player_api.put(f"{table['url']}/instance/backup", data={})
    assert again.status == 409
    assert again.json()["needs"] == "overwrite" and again.json()["backup"]["level"] == 1
    overwritten = player_api.put(f"{table['url']}/instance/backup", data={"overwrite": True})
    assert overwritten.ok and overwritten.json()["instance"]["backup"]["level"] == 2


def test_back_up_while_switching_onto_a_roadmap(table: dict, player_api: APIRequestContext):
    character = new_character(player_api)
    roadmap = new_roadmap(player_api, character["id"])
    plan(player_api, roadmap["id"], 2, prefer={"feature:fighter-fighting-style": ["fighter-fighting-style-defense"]})
    bring(player_api, table, character)
    level_up_by_hand(player_api, table, 2)
    by_hand = player_api.get(f"{table['url']}/instance").json()["instance"]["build"]

    followed = player_api.put(f"{table['url']}/instance/roadmap", data={"roadmap_id": roadmap["id"], "backup": True})
    assert followed.ok
    assert followed.json()["instance"]["backup"]["reason"] == "Before following “Champion route”"
    # A second switch with a backup asks before overwriting it
    player_api.delete(f"{table['url']}/instance/roadmap")
    conflict = player_api.put(f"{table['url']}/instance/roadmap", data={"roadmap_id": roadmap["id"], "backup": True})
    assert conflict.status == 409
    assert player_api.get(f"{table['url']}/instance").json()["instance"]["following"] is None   # nothing changed

    # Restoring brings back the hand-picked choices, and stops following
    player_api.put(f"{table['url']}/instance/roadmap", data={"roadmap_id": roadmap["id"]})
    restored = player_api.post(f"{table['url']}/instance/backup/restore").json()["instance"]
    assert restored["build"]["choices"] == by_hand["choices"]
    assert restored["following"] is None
    # ...and the swapped-out backup remembers it was following, so restoring again follows again
    again = player_api.post(f"{table['url']}/instance/backup/restore").json()["instance"]
    assert again["following"]["name"] == "Champion route"


def test_delete_a_backup(table: dict, player_api: APIRequestContext):
    character = new_character(player_api)
    bring(player_api, table, character)
    assert player_api.delete(f"{table['url']}/instance/backup").status == 404
    player_api.put(f"{table['url']}/instance/backup", data={})
    deleted = player_api.delete(f"{table['url']}/instance/backup")
    assert deleted.ok and deleted.json()["instance"]["backup"] is None
    assert player_api.post(f"{table['url']}/instance/backup/restore").status == 404


# ------------------------------------------------------------------ publishing
def test_publish_with_some_roadmaps_and_copies_get_them(user_api: APIRequestContext, other_api: APIRequestContext):
    character = new_character(user_api, name="Roadmapped Hero")
    first = new_roadmap(user_api, character["id"], "Champion route")
    plan_to(user_api, first["id"], 1, 3)
    new_roadmap(user_api, character["id"], "Not ready")
    response = user_api.post("/api/published", data={"character_id": character["id"], "roadmap_ids": [first["id"]]})
    assert response.status == 201, response.text()
    published = response.json()["published"]
    assert published["roadmaps"] == [{"name": "Champion route", "start_level": 1, "end_level": 3}]

    # Later changes to the author's roadmap don't change the published one
    user_api.delete(f"/api/roadmaps/{first['id']}/levels/3")
    copy = other_api.post("/api/characters", data={"published": published["id"]}).json()["character"]
    roadmaps = other_api.get(f"/api/characters/{copy['id']}/roadmaps").json()["roadmaps"]
    assert [(r["name"], r["end_level"]) for r in roadmaps] == [("Champion route", 3)]


def test_publish_with_no_roadmaps(user_api: APIRequestContext, other_api: APIRequestContext):
    character = new_character(user_api, name="Plain Hero")
    new_roadmap(user_api, character["id"])
    published = user_api.post("/api/published", data={"character_id": character["id"]}).json()["published"]
    assert published["roadmaps"] == []
    copy = other_api.post("/api/characters", data={"published": published["id"]}).json()["character"]
    assert other_api.get(f"/api/characters/{copy['id']}/roadmaps").json()["roadmaps"] == []


def test_only_the_characters_own_roadmaps_can_be_published(user_api: APIRequestContext):
    character = new_character(user_api, name="Hero A")
    other = new_character(user_api, name="Hero B")
    roadmap = new_roadmap(user_api, other["id"])
    response = user_api.post("/api/published", data={"character_id": character["id"], "roadmap_ids": [roadmap["id"]]})
    assert response.status == 400
    assert response.json()["errors"]["roadmap_ids"] == "Choose roadmaps that belong to Hero A."


def test_the_same_character_with_different_roadmaps_can_be_published_again(user_api: APIRequestContext):
    character = new_character(user_api, name="Twice Hero")
    roadmap = new_roadmap(user_api, character["id"])
    assert user_api.post("/api/published", data={"character_id": character["id"]}).status == 201
    assert user_api.post("/api/published", data={"character_id": character["id"]}).status == 400
    assert user_api.post("/api/published", data={"character_id": character["id"],
                                                 "roadmap_ids": [roadmap["id"]]}).status == 201
