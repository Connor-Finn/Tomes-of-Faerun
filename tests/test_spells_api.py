"""Spell catalogue API: /api/spells.

Covers searching and filtering the SRD spells, each user's favourites (private to them), and a
spell's page listing which of your characters know it. Which spells a character may learn is the
rules engine's job and is covered in test_character_rules.py.
"""
import pytest
from playwright.sync_api import APIRequestContext

from builds import autofill, blank

pytestmark = pytest.mark.api

SRD_SPELLS = 319


def star(ctx: APIRequestContext, index: str) -> dict:
    response = ctx.put(f"/api/spells/favourites/{index}")
    assert response.ok, response.text()
    return response.json()


def favourite_indexes(ctx: APIRequestContext) -> list[str]:
    return [s["index"] for s in ctx.get("/api/spells/favourites").json()["favourites"]]


# ------------------------------------------------------------------ access
@pytest.mark.parametrize("method,url", [
    ("get", "/api/spells"), ("get", "/api/spells/fireball"), ("get", "/api/spells/favourites"),
    ("put", "/api/spells/favourites/fireball"), ("delete", "/api/spells/favourites/fireball"),
])
def test_the_spell_catalogue_needs_a_login(api: APIRequestContext, method: str, url: str):
    assert getattr(api, method)(url).status == 401


# ------------------------------------------------------------------ the catalogue
def test_every_srd_spell_is_listed(user_api: APIRequestContext):
    body = user_api.get("/api/spells?per_page=500&facets=1").json()
    assert body["count"] == SRD_SPELLS
    assert body["favourite_count"] == 0
    assert all(s["favourite"] is False for s in body["results"])
    assert body["results"][0]["name"] == "Acid Arrow"  # sorted by name
    assert {"level", "school", "class"} <= body["facets"].keys()
    assert body["facets"]["level"][0] == {"value": "0", "label": "Cantrip"}


def test_filter_wizard_cantrips(user_api: APIRequestContext):
    body = user_api.get("/api/spells?level=0&class=wizard&per_page=50").json()
    names = [s["name"] for s in body["results"]]
    assert "Fire Bolt" in names and "Sacred Flame" not in names
    assert all(s["level"] == 0 and "Wizard" in s["classes"] for s in body["results"])


@pytest.mark.parametrize("query,check", [
    ("ritual=1", lambda s: s["ritual"]),
    ("concentration=1", lambda s: s["concentration"]),
    ("concentration=0", lambda s: not s["concentration"]),
    ("school=evocation", lambda s: s["school"] == "Evocation"),
    ("q=fire", lambda s: "fire" in s["name"].lower()),
])
def test_filters(user_api: APIRequestContext, query: str, check):
    body = user_api.get(f"/api/spells?{query}&per_page=500").json()
    assert 0 < body["count"] < SRD_SPELLS
    assert all(check(s) for s in body["results"])


def test_sort_by_level(user_api: APIRequestContext):
    levels = [s["level"] for s in user_api.get("/api/spells?sort=level&per_page=500").json()["results"]]
    assert levels == sorted(levels)


def test_read_one_spell(user_api: APIRequestContext):
    body = user_api.get("/api/spells/fireball").json()
    assert body["spell"]["name"] == "Fireball"
    assert body["spell"]["level"] == 3
    assert body["spell"]["damage"][0]["damage_at_slot_level"]["3"] == "8d6"
    assert body["favourite"] is False
    assert body["characters"] == []


def test_an_unknown_spell_is_a_404(user_api: APIRequestContext):
    response = user_api.get("/api/spells/wish-for-more-wishes")
    assert response.status == 404
    assert "no spell called" in response.json()["error"]
    assert user_api.put("/api/spells/favourites/wish-for-more-wishes").status == 404


# ------------------------------------------------------------------ favourites
def test_star_and_unstar_a_spell(user_api: APIRequestContext):
    assert star(user_api, "fireball") == {"favourite": True, "message": "Fireball is one of your favourites."}
    star(user_api, "shield")
    star(user_api, "fireball")  # starring twice changes nothing
    assert favourite_indexes(user_api) == ["shield", "fireball"]  # by level, then name

    assert user_api.get("/api/spells/fireball").json()["favourite"] is True
    page = user_api.get("/api/spells?q=fire").json()
    assert {s["name"]: s["favourite"] for s in page["results"]}["Fireball"] is True
    assert page["favourite_count"] == 2

    response = user_api.delete("/api/spells/favourites/fireball")
    assert response.json() == {"favourite": False, "message": "Fireball was taken off your favourites."}
    assert user_api.delete("/api/spells/favourites/fireball").ok  # unstarring twice is fine too
    assert favourite_indexes(user_api) == ["shield"]


def test_only_favourites_filter(user_api: APIRequestContext):
    for index in ("fireball", "fire-bolt", "cure-wounds"):
        star(user_api, index)
    body = user_api.get("/api/spells?favourites=1").json()
    assert [s["name"] for s in body["results"]] == ["Cure Wounds", "Fire Bolt", "Fireball"]
    # ...and it combines with the other filters
    body = user_api.get("/api/spells?favourites=1&level=0").json()
    assert [s["name"] for s in body["results"]] == ["Fire Bolt"]


def test_favourites_are_private(user_api: APIRequestContext, other_api: APIRequestContext):
    star(user_api, "fireball")
    assert favourite_indexes(other_api) == []
    assert other_api.get("/api/spells/fireball").json()["favourite"] is False
    assert other_api.get("/api/spells?favourites=1").json()["count"] == 0


# ------------------------------------------------------------------ characters who know a spell
def _check(ctx: APIRequestContext):
    return lambda build: ctx.post("/api/characters/check", data={"build": build}).json()


def test_a_spell_lists_your_characters_who_know_it(user_api: APIRequestContext, other_api: APIRequestContext):
    build = autofill(_check(user_api), blank(name="Mira", **{"class": "wizard"}),
                     prefer={"spells:spellbook": ["magic-missile"], "spells:cantrips": ["fire-bolt"]})
    response = user_api.post("/api/characters", data={"build": build})
    assert response.status == 201, response.text()
    mira = response.json()["character"]

    assert user_api.get("/api/spells/magic-missile").json()["characters"] == [
        {"id": mira["id"], "name": "Mira", "sources": ["Spellbook"]}]
    assert user_api.get("/api/spells/fire-bolt").json()["characters"][0]["sources"] == ["Cantrip"]
    assert user_api.get("/api/spells/fireball").json()["characters"] == []
    # Other players never see your characters
    assert other_api.get("/api/spells/magic-missile").json()["characters"] == []
