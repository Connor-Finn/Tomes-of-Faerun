"""Items catalogue API: /api/items, and items added to characters.

Covers searching and filtering SRD equipment and magic items together, each user's favourites
(private to them), an item's page listing which of your characters carry it, and the house rule
that players may add any catalogue item to a character on top of the starting equipment.
"""
import pytest
from playwright.sync_api import APIRequestContext

from builds import aldric

pytestmark = pytest.mark.api

SRD_EQUIPMENT = 237
SRD_MAGIC_ITEMS = 239  # magic items with variants ("Armor, +1, +2, or +3") are listed once
SRD_ITEMS = SRD_EQUIPMENT + SRD_MAGIC_ITEMS


def items(ctx: APIRequestContext, query: str = "") -> dict:
    response = ctx.get(f"/api/items?per_page=500&{query}")
    assert response.ok, response.text()
    return response.json()


def names(ctx: APIRequestContext, query: str) -> list[str]:
    return [i["name"] for i in items(ctx, query)["results"]]


def star(ctx: APIRequestContext, index: str) -> dict:
    response = ctx.put(f"/api/items/favourites/{index}")
    assert response.ok, response.text()
    return response.json()


def create(ctx: APIRequestContext, build: dict) -> APIRequestContext:
    return ctx.post("/api/characters", data={"build": build})


def check(ctx: APIRequestContext, build: dict) -> dict:
    response = ctx.post("/api/characters/check", data={"build": build})
    assert response.ok, response.text()
    return response.json()


def inventory_row(sheet: dict, index: str) -> dict | None:
    return next((i for i in sheet["inventory"] if i["index"] == index), None)


# ------------------------------------------------------------------ access
@pytest.mark.parametrize("method,url", [
    ("get", "/api/items"), ("get", "/api/items/longsword"), ("get", "/api/items/favourites"),
    ("put", "/api/items/favourites/longsword"), ("delete", "/api/items/favourites/longsword"),
])
def test_the_items_catalogue_needs_a_login(api: APIRequestContext, method: str, url: str):
    assert getattr(api, method)(url).status == 401


# ------------------------------------------------------------------ the catalogue
def test_equipment_and_magic_items_are_one_catalogue(user_api: APIRequestContext):
    body = items(user_api, "facets=1")
    assert body["count"] == SRD_ITEMS
    assert body["favourite_count"] == 0
    assert [r["name"] for r in body["results"][:3]] == ["Abacus", "Acid (vial)", "Adamantine Armor"]
    assert {r["kind"] for r in body["results"]} == {"equipment", "magic"}
    assert [k["value"] for k in body["facets"]["kind"]] == ["equipment", "magic"]
    assert [r["label"] for r in body["facets"]["rarity"]] == [
        "Common", "Uncommon", "Rare", "Very Rare", "Legendary", "Artifact", "Varies"]
    categories = {c["value"] for c in body["facets"]["category"]}
    assert {"weapon", "armor", "adventuring-gear", "wondrous-items", "potion", "ring"} <= categories


def test_filter_by_kind(user_api: APIRequestContext):
    assert items(user_api, "kind=equipment")["count"] == SRD_EQUIPMENT
    assert items(user_api, "kind=magic")["count"] == SRD_MAGIC_ITEMS
    assert user_api.get("/api/items?kind=cursed").status == 400


def test_search_finds_both_kinds(user_api: APIRequestContext):
    found = items(user_api, "q=rope")["results"]
    assert [(r["name"], r["kind"]) for r in found] == [
        ("Rope of Climbing", "magic"), ("Rope of Entanglement", "magic"),
        ("Rope, hempen (50 feet)", "equipment"), ("Rope, silk (50 feet)", "equipment"),
    ]


def test_summaries_say_what_an_item_is(user_api: APIRequestContext):
    by_name = {r["name"]: r for r in items(user_api, "q=sword")["results"]}
    longsword = by_name["Longsword"]
    assert (longsword["type"], longsword["cost"], longsword["weight"], longsword["rarity"]) == (
        "Martial Melee weapon", "15 gp", 3, None)
    vorpal = by_name["Vorpal Sword"]
    assert vorpal["kind"] == "magic"
    assert vorpal["rarity"] == "Legendary"
    assert vorpal["attunement"] == "requires attunement"
    assert vorpal["cost"] is None


def test_filter_magic_items_by_rarity_and_category(user_api: APIRequestContext):
    assert names(user_api, "category=ring&rarity=legendary") == [
        "Ring of Djinni Summoning", "Ring of Elemental Command", "Ring of Invisibility",
        "Ring of Spell Turning", "Ring of Three Wishes"]
    # Equipment has no rarity, so a rarity filter means magic items only
    assert {r["kind"] for r in items(user_api, "rarity=uncommon")["results"]} == {"magic"}


def test_weapons_of_both_kinds_share_a_category(user_api: APIRequestContext):
    weapons = items(user_api, "category=weapon")["results"]
    assert {r["kind"] for r in weapons} == {"equipment", "magic"}
    assert len([r for r in weapons if r["kind"] == "equipment"]) == 37


def test_attunement_filter(user_api: APIRequestContext):
    attuned = items(user_api, "attunement=1")["results"]
    assert attuned and all(r["attunement"] for r in attuned)
    assert all(not r["attunement"] for r in items(user_api, "attunement=0")["results"])


def test_sort_by_cost_and_rarity(user_api: APIRequestContext):
    by_cost = items(user_api, "kind=equipment&sort=cost")["results"]
    costs = [r["cost"] for r in by_cost]
    assert costs[0].endswith("cp")
    assert by_cost[-1]["name"] == "Galley"  # 30,000 gp
    assert items(user_api, "kind=magic&sort=rarity&order=desc")["results"][0]["rarity"] == "Varies"
    assert user_api.get("/api/items?sort=sparkle").status == 400


def test_paging(user_api: APIRequestContext):
    body = user_api.get("/api/items?per_page=25&page=3").json()
    assert (body["page"], body["pages"], len(body["results"])) == (3, 20, 25)


# ------------------------------------------------------------------ one item
def test_an_items_page(user_api: APIRequestContext):
    body = user_api.get("/api/items/bag-of-holding").json()
    assert body["kind"] == "magic"
    assert body["item"]["name"] == "Bag of Holding"
    assert body["item"]["desc"][1].startswith("This bag has an interior space")
    assert body["summary"]["rarity"] == "Uncommon"
    assert body["favourite"] is False
    assert body["characters"] == []

    sword = user_api.get("/api/items/longsword").json()
    assert sword["kind"] == "equipment"
    assert sword["item"]["damage"]["damage_dice"] == "1d8"


def test_a_missing_item(user_api: APIRequestContext):
    response = user_api.get("/api/items/sword-of-a-thousand-truths")
    assert response.status == 404
    assert "no item called" in response.json()["error"]


# ------------------------------------------------------------------ favourites
def test_star_and_unstar_items(user_api: APIRequestContext):
    assert star(user_api, "bag-of-holding")["message"] == "Bag of Holding is one of your favourites."
    star(user_api, "rope-hempen-50-feet")
    star(user_api, "rope-hempen-50-feet")  # starring twice is harmless
    favourites = user_api.get("/api/items/favourites").json()["favourites"]
    assert [f["name"] for f in favourites] == ["Bag of Holding", "Rope, hempen (50 feet)"]

    body = items(user_api, "favourites=1")
    assert body["count"] == 2 and body["favourite_count"] == 2
    assert all(r["favourite"] for r in body["results"])
    assert user_api.get("/api/items/bag-of-holding").json()["favourite"] is True

    response = user_api.delete("/api/items/favourites/bag-of-holding")
    assert response.json()["message"] == "Bag of Holding was taken off your favourites."
    assert names(user_api, "favourites=1") == ["Rope, hempen (50 feet)"]


def test_favourites_are_private(user_api: APIRequestContext, other_api: APIRequestContext):
    star(user_api, "potion-of-healing")
    assert items(other_api, "favourites=1")["count"] == 0
    assert other_api.get("/api/items/potion-of-healing").json()["favourite"] is False


def test_cant_star_an_item_that_doesnt_exist(user_api: APIRequestContext):
    assert user_api.put("/api/items/favourites/the-one-ring").status == 404


# ------------------------------------------------------------------ items on characters
def test_added_items_join_the_starting_kit(user_api: APIRequestContext):
    build = {**aldric(), "items": {"bag-of-holding": 1, "torch": 3, "longbow": 1}}
    response = create(user_api, build)
    assert response.status == 201, response.text()
    sheet = response.json()["sheet"]

    bag = inventory_row(sheet, "bag-of-holding")
    assert (bag["kind"], bag["rarity"], bag["added"], bag["quantity"]) == ("magic", "Uncommon", 1, 1)
    torch = inventory_row(sheet, "torch")
    assert (torch["added"], torch["quantity"]) == (3, 3)
    sword = inventory_row(sheet, "longsword")  # from the fighter's starting kit
    assert sword["added"] == 0
    # An added weapon is a weapon like any other
    assert "Longbow" in [a["name"] for a in sheet["attacks"]]


def test_added_armour_can_be_worn(user_api: APIRequestContext):
    build = {**aldric(), "items": {"plate-armor": 1}, "equipped": {"armor": "plate-armor", "shield": "shield"}}
    result = check(user_api, build)
    assert result["valid"], result["errors"]
    assert result["sheet"]["armor_class"] == 20  # plate 18 + shield 2
    assert result["sheet"]["armor_class_note"].startswith("Plate Armor")


def test_bad_items_are_refused(user_api: APIRequestContext):
    result = check(user_api, {**aldric(), "items": {"the-one-ring": 1, "torch": 0, "rope-hempen-50-feet": "lots"}})
    assert not result["valid"]
    messages = {e["field"]: e["message"] for e in result["errors"]}
    assert "no item called" in messages["items.the-one-ring"]
    assert "whole number from 1 to 999" in messages["items.torch"]
    assert "whole number from 1 to 999" in messages["items.rope-hempen-50-feet"]

    response = create(user_api, {**aldric(), "items": {"torch": 1000}})
    assert response.status == 400

    assert not check(user_api, {**aldric(), "items": ["torch"]})["valid"]


def test_added_items_are_saved_and_can_be_changed(user_api: APIRequestContext):
    character = create(user_api, {**aldric(), "items": {"potion-of-healing": 2}}).json()["character"]
    url = f"/api/characters/{character['id']}"
    assert user_api.get(url).json()["character"]["build"]["items"] == {"potion-of-healing": 2}

    build = {**aldric(), "items": {}}
    response = user_api.patch(url, data={"build": build})
    assert response.ok, response.text()
    assert inventory_row(response.json()["sheet"], "potion-of-healing") is None


def test_an_item_shows_which_characters_carry_it(user_api: APIRequestContext, other_api: APIRequestContext):
    create(user_api, {**aldric(), "name": "Brannoc", "items": {"rope-hempen-50-feet": 2}})
    create(other_api, {**aldric(), "name": "Someone Else", "items": {"rope-hempen-50-feet": 1}})
    carriers = user_api.get("/api/items/rope-hempen-50-feet").json()["characters"]
    # Aldric's dungeoneer's pack holds a rope too, but packs are counted as one item
    assert [(c["name"], c["quantity"], c["added"]) for c in carriers] == [("Brannoc", 2, True)]

    sword = user_api.get("/api/items/longsword").json()["characters"]
    assert [(c["name"], c["added"]) for c in sword] == [("Brannoc", False)]
