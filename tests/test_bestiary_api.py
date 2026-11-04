"""Bestiary API: /api/bestiary.

Covers a DM's monster collections (roles, counts, notes, XP totals), their own environment groups,
and that nobody else can see or change them. The SRD monster data itself is covered in
test_rules_api.py.
"""
import pytest
from playwright.sync_api import APIRequestContext

pytestmark = pytest.mark.api


def new_collection(ctx: APIRequestContext, name: str = "Warlock boss dungeon", **extra) -> dict:
    response = ctx.post("/api/bestiary/collections", data={"name": name, **extra})
    assert response.status == 201, response.text()
    return response.json()["collection"]


def add(ctx: APIRequestContext, collection_id: int, monster: str, **extra) -> dict:
    response = ctx.post(f"/api/bestiary/collections/{collection_id}/monsters", data={"monster": monster, **extra})
    assert response.status == 201, response.text()
    return response.json()


def new_environment(ctx: APIRequestContext, name: str = "Underdark") -> dict:
    response = ctx.post("/api/bestiary/environments", data={"name": name})
    assert response.status == 201, response.text()
    return response.json()["environment"]


# ------------------------------------------------------------------ access
@pytest.mark.parametrize("method,url", [
    ("get", "/api/bestiary/monsters"), ("get", "/api/bestiary/monsters/goblin"),
    ("get", "/api/bestiary/collections"), ("post", "/api/bestiary/collections"),
    ("get", "/api/bestiary/collections/1"), ("patch", "/api/bestiary/collections/1"),
    ("delete", "/api/bestiary/collections/1"), ("post", "/api/bestiary/collections/1/monsters"),
    ("get", "/api/bestiary/environments"), ("post", "/api/bestiary/environments"),
    ("put", "/api/bestiary/environments/1/monsters/goblin"),
])
def test_the_bestiary_needs_a_login(api: APIRequestContext, method: str, url: str):
    response = getattr(api, method)(url, **({} if method in ("get", "delete", "put") else {"data": {}}))
    assert response.status == 401


def test_other_dms_cant_see_or_change_your_collections(user_api: APIRequestContext, other_api: APIRequestContext):
    collection = new_collection(user_api)
    entry = add(user_api, collection["id"], "goblin")["collection"]["entries"][0]
    url = f"/api/bestiary/collections/{collection['id']}"

    assert other_api.get(url).status == 404
    assert other_api.patch(url, data={"name": "Mine now"}).status == 404
    assert other_api.delete(url).status == 404
    assert other_api.post(f"{url}/monsters", data={"monster": "orc"}).status == 404
    assert other_api.delete(f"{url}/monsters/{entry['id']}").status == 404
    assert other_api.get("/api/bestiary/collections").json()["collections"] == []
    # ...and the monster page doesn't leak it either
    assert other_api.get("/api/bestiary/monsters/goblin").json()["collections"] == []
    assert user_api.get(url).json()["collection"]["name"] == "Warlock boss dungeon"


def test_other_dms_cant_use_your_environments(user_api: APIRequestContext, other_api: APIRequestContext):
    env = new_environment(user_api)
    url = f"/api/bestiary/environments/{env['id']}"
    assert other_api.put(f"{url}/monsters/goblin").status == 404
    assert other_api.patch(url, data={"name": "Overdark"}).status == 404
    assert other_api.delete(url).status == 404
    assert other_api.get(f"/api/bestiary/monsters?environment={env['id']}").status == 404


# ------------------------------------------------------------------ monsters
def test_a_monster_page_has_the_full_stat_block(user_api: APIRequestContext):
    body = user_api.get("/api/bestiary/monsters/adult-red-dragon").json()
    assert body["monster"]["name"] == "Adult Red Dragon"
    assert body["monster"]["hit_points"] == 256
    assert body["cr"] == "17"
    assert body["collections"] == [] and body["environments"] == []


def test_an_unknown_monster_is_404(user_api: APIRequestContext):
    response = user_api.get("/api/bestiary/monsters/tarrasque-jr")
    assert response.status == 404
    assert "no monster called 'tarrasque-jr'" in response.json()["error"]


def test_the_monster_list_keeps_the_rules_filters(user_api: APIRequestContext):
    body = user_api.get("/api/bestiary/monsters?type=dragon&cr_min=17&sort=cr&order=desc&per_page=5").json()
    assert body["count"] > 0
    assert all(m["type"] == "dragon" and m["challenge_rating"] >= 17 for m in body["results"])
    crs = [m["challenge_rating"] for m in body["results"]]
    assert crs == sorted(crs, reverse=True)


# ------------------------------------------------------------------ collections
def test_a_new_dm_has_no_collections(user_api: APIRequestContext):
    body = user_api.get("/api/bestiary/collections").json()
    assert body == {"collections": [], "limit": 100}


def test_create_a_collection(user_api: APIRequestContext):
    collection = new_collection(user_api, notes="  The warlock waits in the crypt.  ")
    assert collection["name"] == "Warlock boss dungeon"
    assert collection["notes"] == "The warlock waits in the crypt."
    assert collection["entries"] == []
    assert collection["monster_count"] == 0 and collection["total_xp"] == 0


@pytest.mark.parametrize("name,message", [
    ("", "Give the collection a name."),
    ("   ", "Give the collection a name."),
    ("x" * 61, "Keep the name to 60 characters or fewer."),
])
def test_a_collection_needs_a_sensible_name(user_api: APIRequestContext, name: str, message: str):
    response = user_api.post("/api/bestiary/collections", data={"name": name})
    assert response.status == 400
    assert response.json()["errors"] == {"name": message}


def test_collection_names_are_unique_per_dm(user_api: APIRequestContext, other_api: APIRequestContext):
    new_collection(user_api, "Goblin warren")
    response = user_api.post("/api/bestiary/collections", data={"name": "GOBLIN WARREN"})
    assert response.status == 400
    assert response.json()["errors"]["name"] == "You already have a collection with that name."
    new_collection(other_api, "Goblin warren")  # another DM can use the same name


def test_add_monsters_with_roles_and_counts(user_api: APIRequestContext):
    collection = new_collection(user_api)
    add(user_api, collection["id"], "goblin", role="minion", count=6)
    add(user_api, collection["id"], "hobgoblin", role="elite", count=2)
    body = add(user_api, collection["id"], "cult-fanatic", role="boss")
    assert body["message"] == "Cult Fanatic was added to Warlock boss dungeon."

    c = body["collection"]
    assert [(e["monster"]["name"], e["role"], e["count"]) for e in c["entries"]] == [
        ("Goblin", "minion", 6), ("Hobgoblin", "elite", 2), ("Cult Fanatic", "boss", 1)]
    assert c["monster_count"] == 9
    assert c["kinds"] == 3
    # goblin 50 XP, hobgoblin 100 XP, cult fanatic 450 XP
    assert c["total_xp"] == 6 * 50 + 2 * 100 + 450
    assert c["roles"] == {"none": 0, "minion": 6, "elite": 2, "boss": 1}


def test_adding_a_monster_twice_adds_to_its_count(user_api: APIRequestContext):
    collection = new_collection(user_api)
    add(user_api, collection["id"], "goblin", role="minion", count=4)
    body = add(user_api, collection["id"], "goblin", count=2)
    assert body["message"] == "Warlock boss dungeon now has 6 × Goblin."
    [entry] = body["collection"]["entries"]
    assert entry["count"] == 6
    assert entry["role"] == "minion"  # not sent, so it keeps its role


def test_counts_stop_at_99(user_api: APIRequestContext):
    collection = new_collection(user_api)
    add(user_api, collection["id"], "rat", count=90)
    [entry] = add(user_api, collection["id"], "rat", count=20)["collection"]["entries"]
    assert entry["count"] == 99


@pytest.mark.parametrize("body,message", [
    ({"monster": "goblin", "role": "overlord"}, "Role must be one of"),
    ({"monster": "goblin", "count": 0}, "Count must be a whole number from 1 to 99."),
    ({"monster": "goblin", "count": 100}, "Count must be a whole number from 1 to 99."),
    ({"monster": "goblin", "count": "3"}, "Count must be a whole number from 1 to 99."),
    ({"monster": "goblin", "count": True}, "Count must be a whole number from 1 to 99."),
])
def test_bad_roles_and_counts_are_refused(user_api: APIRequestContext, body: dict, message: str):
    collection = new_collection(user_api)
    response = user_api.post(f"/api/bestiary/collections/{collection['id']}/monsters", data=body)
    assert response.status == 400
    assert message in response.json()["error"]


def test_only_srd_monsters_can_be_added(user_api: APIRequestContext):
    collection = new_collection(user_api)
    response = user_api.post(f"/api/bestiary/collections/{collection['id']}/monsters", data={"monster": "beholder"})
    assert response.status == 404  # the beholder isn't in the SRD


def test_change_a_monsters_role_and_count(user_api: APIRequestContext):
    collection = new_collection(user_api)
    entry = add(user_api, collection["id"], "bugbear")["collection"]["entries"][0]
    assert entry["role"] == "none"
    response = user_api.patch(f"/api/bestiary/collections/{collection['id']}/monsters/{entry['id']}",
                              data={"role": "boss", "count": 3, "note": "Leads the ambush"})
    assert response.ok, response.text()
    [entry] = response.json()["collection"]["entries"]
    assert (entry["role"], entry["role_label"], entry["count"], entry["note"]) == ("boss", "Boss", 3, "Leads the ambush")
    assert entry["xp"] == 3 * 200


def test_remove_a_monster(user_api: APIRequestContext):
    collection = new_collection(user_api)
    add(user_api, collection["id"], "goblin")
    entry = add(user_api, collection["id"], "orc")["collection"]["entries"][1]
    response = user_api.delete(f"/api/bestiary/collections/{collection['id']}/monsters/{entry['id']}")
    assert response.ok
    assert response.json()["message"] == "Orc was removed from Warlock boss dungeon."
    assert [e["monster"]["index"] for e in response.json()["collection"]["entries"]] == ["goblin"]


def test_rename_and_write_notes(user_api: APIRequestContext):
    collection = new_collection(user_api)
    url = f"/api/bestiary/collections/{collection['id']}"
    body = user_api.patch(url, data={"name": "The Hollow Crypt", "notes": "Boss on the altar."}).json()["collection"]
    assert (body["name"], body["notes"]) == ("The Hollow Crypt", "Boss on the altar.")
    # Renaming to its own name (in another case) is fine
    assert user_api.patch(url, data={"name": "the hollow crypt"}).ok
    assert user_api.patch(url, data={"notes": "x" * 2001}).status == 400


def test_delete_a_collection(user_api: APIRequestContext):
    collection = new_collection(user_api)
    add(user_api, collection["id"], "goblin")
    response = user_api.delete(f"/api/bestiary/collections/{collection['id']}")
    assert response.json()["message"] == "Warlock boss dungeon was deleted."
    assert user_api.get(f"/api/bestiary/collections/{collection['id']}").status == 404
    assert user_api.get("/api/bestiary/monsters/goblin").json()["collections"] == []


def test_the_monster_page_says_where_you_saved_it(user_api: APIRequestContext):
    dungeon = new_collection(user_api, "Warlock boss dungeon")
    road = new_collection(user_api, "Ambush on the road")
    add(user_api, dungeon["id"], "goblin", role="minion", count=4)
    add(user_api, road["id"], "goblin", count=2)
    saved = user_api.get("/api/bestiary/monsters/goblin").json()["collections"]
    assert [(c["name"], c["role"], c["count"]) for c in saved] == [
        ("Ambush on the road", "none", 2), ("Warlock boss dungeon", "minion", 4)]


# ------------------------------------------------------------------ environments
def test_environments_group_monsters_and_filter_the_bestiary(user_api: APIRequestContext):
    env = new_environment(user_api, "Underdark")
    for monster in ("drow", "roper", "goblin"):
        response = user_api.put(f"/api/bestiary/environments/{env['id']}/monsters/{monster}")
        assert response.ok, response.text()
    assert response.json()["message"] == "Goblin lives in Underdark."

    listed = user_api.get(f"/api/bestiary/monsters?environment={env['id']}&sort=cr").json()
    assert listed["count"] == 3
    assert [m["name"] for m in listed["results"]] == ["Drow", "Goblin", "Roper"]  # by CR, then name

    # Search and filters still apply inside an environment
    assert user_api.get(f"/api/bestiary/monsters?environment={env['id']}&q=gob").json()["count"] == 1

    envs = user_api.get("/api/bestiary/environments").json()["environments"]
    assert envs[0]["monster_count"] == 3
    assert user_api.get("/api/bestiary/monsters/drow").json()["environments"] == [{"id": env["id"], "name": "Underdark"}]


def test_adding_a_monster_to_an_environment_twice_is_harmless(user_api: APIRequestContext):
    env = new_environment(user_api)
    user_api.put(f"/api/bestiary/environments/{env['id']}/monsters/goblin")
    body = user_api.put(f"/api/bestiary/environments/{env['id']}/monsters/goblin").json()
    assert body["environment"]["monster_count"] == 1


def test_take_a_monster_out_of_an_environment(user_api: APIRequestContext):
    env = new_environment(user_api)
    user_api.put(f"/api/bestiary/environments/{env['id']}/monsters/goblin")
    body = user_api.delete(f"/api/bestiary/environments/{env['id']}/monsters/goblin").json()
    assert body["message"] == "Goblin was taken out of Underdark."
    assert body["environment"]["monsters"] == []


def test_environment_names_are_checked(user_api: APIRequestContext):
    new_environment(user_api, "Swamp")
    for name, message in [("", "Give the environment a name."),
                          ("swamp", "You already have an environment with that name."),
                          ("x" * 41, "Keep the name to 40 characters or fewer.")]:
        response = user_api.post("/api/bestiary/environments", data={"name": name})
        assert response.status == 400
        assert response.json()["errors"] == {"name": message}


def test_rename_and_delete_an_environment(user_api: APIRequestContext):
    env = new_environment(user_api, "Swamp")
    url = f"/api/bestiary/environments/{env['id']}"
    assert user_api.patch(url, data={"name": "Haunted swamp"}).json()["environment"]["name"] == "Haunted swamp"
    assert user_api.delete(url).json()["message"] == "Haunted swamp was deleted. Its monsters are still in the bestiary."
    assert user_api.get("/api/bestiary/environments").json()["environments"] == []
