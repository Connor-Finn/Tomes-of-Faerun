"""Rules content API: the SRD catalogues the bestiary, spellbook and character builder are built on."""
from fractions import Fraction

import pytest
from playwright.sync_api import APIRequestContext

pytestmark = pytest.mark.api


def test_index_lists_every_category_with_counts(api: APIRequestContext):
    kinds = {k["kind"]: k["count"] for k in api.get("/api/rules").json()["kinds"]}
    assert kinds["spells"] == 319
    assert kinds["monsters"] == 334
    assert kinds["classes"] == 12
    assert kinds["races"] == 9


def test_list_is_paginated(api: APIRequestContext):
    body = api.get("/api/rules/monsters", params={"per_page": 10, "page": 2}).json()
    assert body["page"] == 2
    assert body["per_page"] == 10
    assert len(body["results"]) == 10
    assert body["pages"] == 34


def test_search_by_name(api: APIRequestContext):
    names = [s["name"] for s in api.get("/api/rules/spells", params={"q": "fire"}).json()["results"]]
    assert "Fireball" in names
    assert all("fire" in n.lower() for n in names)


def test_spell_filters_combine(api: APIRequestContext):
    body = api.get("/api/rules/spells", params={"level": "3", "class": "wizard", "concentration": "true"}).json()
    assert body["count"] > 0
    for spell in body["results"]:
        assert spell["level"] == 3
        assert "Wizard" in spell["classes"]
        assert spell["concentration"] is True


def test_spell_facets_describe_the_filters(api: APIRequestContext):
    facets = api.get("/api/rules/spells", params={"facets": "1", "per_page": 1}).json()["facets"]
    assert {"value": "0", "label": "Cantrip"} in facets["level"]
    assert {"value": "evocation", "label": "Evocation"} in facets["school"]
    assert {"value": "warlock", "label": "Warlock"} in facets["class"]


@pytest.mark.parametrize("cr_min, cr_max", [("1/4", "1"), ("5", "10"), ("20", "30")])
def test_monster_challenge_rating_range(api: APIRequestContext, cr_min, cr_max):
    body = api.get("/api/rules/monsters", params={"cr_min": cr_min, "cr_max": cr_max, "per_page": 500}).json()
    lo, hi = Fraction(cr_min), Fraction(cr_max)
    assert body["count"] > 0
    assert all(lo <= m["challenge_rating"] <= hi for m in body["results"])


def test_monsters_sort_by_challenge_rating(api: APIRequestContext):
    results = api.get("/api/rules/monsters", params={"type": "dragon", "sort": "cr", "order": "desc"}).json()["results"]
    crs = [m["challenge_rating"] for m in results]
    assert crs == sorted(crs, reverse=True)
    assert results[0]["cr"] in ("24", "22", "21", "20")


def test_monster_detail_has_stat_block(api: APIRequestContext):
    dragon = api.get("/api/rules/monsters/adult-red-dragon").json()
    assert dragon["name"] == "Adult Red Dragon"
    assert dragon["hit_points"] == 256
    assert any(a["name"].startswith("Fire Breath") for a in dragon["actions"])
    assert dragon["legendary_actions"]


def test_links_point_at_our_own_api(api: APIRequestContext):
    fireball = api.get("/api/rules/spells/fireball").json()
    assert fireball["school"]["url"] == "/api/rules/magic-schools/evocation"
    assert api.get(fireball["school"]["url"]).ok


def test_equipment_filter_by_category(api: APIRequestContext):
    results = api.get("/api/rules/equipment", params={"category": "armor", "per_page": 100}).json()["results"]
    assert {r["category"] for r in results} == {"Armor"}
    assert any(r["name"] == "Chain Mail" for r in results)


def test_magic_items_hide_variants_unless_asked(api: APIRequestContext):
    base = api.get("/api/rules/magic-items", params={"q": "potion of healing"}).json()
    every = api.get("/api/rules/magic-items", params={"q": "potion of healing", "include_variants": "1"}).json()
    assert every["count"] > base["count"]


def test_unknown_category_and_entry_return_404(api: APIRequestContext):
    assert api.get("/api/rules/vehicles").status == 404
    assert api.get("/api/rules/spells/not-a-spell").status == 404


def test_bad_filter_value_returns_400(api: APIRequestContext):
    response = api.get("/api/rules/monsters", params={"cr_min": "lots"})
    assert response.status == 400
    assert "cr_min" in response.json()["error"]
