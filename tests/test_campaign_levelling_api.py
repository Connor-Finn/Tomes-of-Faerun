"""Character rules in campaigns: levelling, hit points, locked picks and the DM's control panel.

Agreed with Connor on 2026-11-04 (notes/character-rules.md). The story: a DM runs a campaign and
picks how characters level (by hand or by XP) and how they gain hit points. Mira brings her
character, whose earlier picks are now locked: she levels up one level at a time through the guided
Level Up. The DM never changes her picks, but sets levels and XP, hands out items and spells, and
sends her notes.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import APIRequestContext, Playwright

from builds import aldric, autofill, blank, level_up
from conftest import API_HEADERS

pytestmark = pytest.mark.api


# ------------------------------------------------------------------ helpers
def login(playwright: Playwright, base_url: str, someone: dict) -> APIRequestContext:
    ctx = playwright.request.new_context(base_url=base_url, extra_http_headers=API_HEADERS)
    assert ctx.post("/api/auth/login", data={"email": someone["email"], "password": someone["password"]}).ok
    return ctx


def checker(ctx: APIRequestContext):
    def check(build: dict) -> dict:
        return ctx.post("/api/characters/check", data={"build": build}).json()
    return check


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
    """A campaign with Mira in its party (user_api is the DM)."""
    party = user_api.post("/api/parties", data={"name": "The Lantern Bearers"}).json()["party"]
    assert user_api.post(f"/api/parties/{party['id']}/invites", data={"email": player["email"]}).status == 201
    assert player_api.post(f"/api/parties/{party['id']}/accept").ok
    campaign = user_api.post("/api/campaigns", data={"name": "The Whispering Dead"}).json()["campaign"]
    assert user_api.patch(f"/api/campaigns/{campaign['id']}", data={"party_id": party["id"]}).ok
    return {"campaign": campaign, "url": f"/api/campaigns/{campaign['id']}"}


def bring(ctx: APIRequestContext, table: dict, build: dict | None = None, name: str = "Aldric Vane") -> dict:
    character = ctx.post("/api/characters", data={"build": {**(build or aldric()), "name": name}}).json()["character"]
    response = ctx.post(f"{table['url']}/instance", data={"character_id": character["id"]})
    assert response.status == 201, response.text()
    instance = response.json()["instance"]
    return {**instance, "dm_url": f"{table['url']}/instances/{instance['id']}"}


def mine(ctx: APIRequestContext, table: dict) -> dict:
    return ctx.get(f"{table['url']}/instance").json()


def set_rules(dm: APIRequestContext, table: dict, **rules) -> dict:
    response = dm.put(f"{table['url']}/rules", data=rules)
    assert response.ok, response.text()
    return response.json()["campaign"]["rules"]


# ------------------------------------------------------------------ rolled ability scores
def test_the_app_rolls_once_and_the_roll_is_kept(user_api: APIRequestContext):
    first = user_api.post("/api/characters/ability-rolls")
    assert first.status == 201
    roll = first.json()["roll"]
    assert len(roll["rolls"]) == 6 and all(3 <= r <= 18 for r in roll["rolls"])
    assert all(sum(d[:3]) == r for d, r in zip(roll["dice"], roll["rolls"]))   # 4d6, lowest dropped
    # Asking again (a refresh) gives the same roll: no rerolls
    again = user_api.post("/api/characters/ability-rolls")
    assert again.status == 200 and again.json()["roll"] == roll


def test_a_character_built_with_the_roll_claims_it(user_api: APIRequestContext):
    roll = user_api.post("/api/characters/ability-rolls").json()["roll"]
    base = dict(zip(["str", "dex", "con", "int", "wis", "cha"], sorted(roll["rolls"], reverse=True)))
    scores = {"method": "roll", "rolls": roll["rolls"], "roll_id": roll["id"], "base": base}
    response = user_api.post("/api/characters", data={"build": {**aldric(), "ability_scores": scores}})
    assert response.status == 201, response.text()
    assert response.json()["sheet"]["ability_method"] == "Rolled (4d6, drop the lowest)"
    # The next character gets a fresh roll
    assert user_api.post("/api/characters/ability-rolls").json()["roll"]["id"] != roll["id"]
    # ...and the claimed roll can't be used again for another character
    reused = user_api.post("/api/characters", data={"build": {**aldric(), "ability_scores": scores}})
    assert reused.status == 400


def test_you_cant_roll_your_own_scores(user_api: APIRequestContext, other_api: APIRequestContext):
    roll = user_api.post("/api/characters/ability-rolls").json()["roll"]
    perfect = {"method": "roll", "rolls": [18] * 6, "roll_id": roll["id"],
               "base": {k: 18 for k in ("str", "dex", "con", "int", "wis", "cha")}}
    assert user_api.post("/api/characters", data={"build": {**aldric(), "ability_scores": perfect}}).status == 400
    # nor use someone else's roll
    base = dict(zip(["str", "dex", "con", "int", "wis", "cha"], roll["rolls"]))
    theirs = {"method": "roll", "rolls": roll["rolls"], "roll_id": roll["id"], "base": base}
    assert other_api.post("/api/characters", data={"build": {**aldric(), "ability_scores": theirs}}).status == 400


def test_rolled_scores_must_use_each_roll_once(user_api: APIRequestContext):
    result = user_api.post("/api/characters/check", data={"build": {**aldric(), "ability_scores": {
        "method": "roll", "rolls": [15, 14, 13, 12, 10, 8],
        "base": {"str": 15, "dex": 15, "con": 13, "int": 12, "wis": 10, "cha": 8}}}}).json()
    assert "Use each of your rolls (15, 14, 13, 12, 10, 8) once." in [e["message"] for e in result["errors"]]


def test_base_characters_never_keep_campaign_only_fields(user_api: APIRequestContext):
    build = {**aldric(), "given": {"bag-of-holding": 1}, "hp_levels": {"2": {"method": "max", "die": 10}},
             "granted_spells": ["fireball"]}
    saved = user_api.post("/api/characters", data={"build": build}).json()["character"]["build"]
    assert not {"given", "hp_levels", "granted_spells"} & set(saved)


# ------------------------------------------------------------------ campaign rules
def test_campaign_rules_default_to_manual_with_average_or_roll(table: dict, player_api: APIRequestContext):
    rules = player_api.get(table["url"]).json()["campaign"]["rules"]
    assert rules == {"levelling": "manual", "levelling_label": "Manual", "hp_methods": ["average", "roll"]}


def test_only_the_dm_sets_the_rules(table: dict, user_api: APIRequestContext, player_api: APIRequestContext):
    assert player_api.put(f"{table['url']}/rules", data={"levelling": "xp"}).status == 403
    rules = set_rules(user_api, table, levelling="xp", hp_methods=["max", "average"])
    assert rules == {"levelling": "xp", "levelling_label": "Experience points", "hp_methods": ["average", "max"]}
    bad = user_api.put(f"{table['url']}/rules", data={"levelling": "milestones", "hp_methods": []})
    assert bad.status == 400 and set(bad.json()["errors"]) == {"levelling", "hp_methods"}


# ------------------------------------------------------------------ levelling
def test_manual_levelling_shows_what_the_level_brings(table: dict, player_api: APIRequestContext):
    bring(player_api, table)
    preview = player_api.get(f"{table['url']}/instance/level-up").json()["level_up"]
    assert preview["allowed"] and preview["level"] == 2
    assert "New feature: Action Surge (1 use)." in preview["changes"]
    assert [m["value"] for m in preview["hp"]["methods"]] == ["average", "roll"]
    average = preview["hp"]["methods"][0]
    assert (average["die"], preview["hp"]["hit_die"]) == (6, 10)


def test_a_level_up_is_one_level_at_a_time(table: dict, player_api: APIRequestContext):
    bring(player_api, table)
    preview = player_api.get(f"{table['url']}/instance/level-up").json()["level_up"]
    response = player_api.post(f"{table['url']}/instance/level-up",
                               data={"build": {**preview["build"], "level": 3}, "hp_method": "average"})
    assert response.ok   # the level comes from the server, not the request
    assert response.json()["instance"]["level"] == 2


def test_xp_levelling_waits_for_the_threshold(table: dict, user_api: APIRequestContext, player_api: APIRequestContext):
    set_rules(user_api, table, levelling="xp")
    bring(player_api, table)
    blocked = player_api.get(f"{table['url']}/instance/level-up").json()["level_up"]
    assert blocked == {"allowed": False, "level": 2, "reason": "Aldric Vane needs 300 more XP to reach level 2."}
    assert player_api.post(f"{table['url']}/instance/level-up", data={"hp_method": "average"}).status == 400

    some = player_api.post(f"{table['url']}/instance/xp", data={"gained": 250}).json()
    assert some["instance"]["progress"]["levels_owed"] == 0
    crossed = player_api.post(f"{table['url']}/instance/xp", data={"gained": 700}).json()
    assert crossed["message"] == "Aldric Vane gained 700 XP (950 in all). Level 2 is ready!"
    assert crossed["instance"]["progress"]["levels_owed"] == 2   # 950 XP is level 3
    body = level_up(player_api, table["url"], 3)
    assert body["instance"]["progress"]["levels_owed"] == 0
    assert player_api.post(f"{table['url']}/instance/xp", data={"gained": 0}).status == 400


def test_xp_only_counts_in_xp_campaigns(table: dict, player_api: APIRequestContext):
    bring(player_api, table)
    response = player_api.post(f"{table['url']}/instance/xp", data={"gained": 300})
    assert response.status == 400 and "levels up by hand" in response.json()["error"]


# ------------------------------------------------------------------ hit points
def test_a_hit_point_roll_is_made_once(table: dict, player_api: APIRequestContext):
    bring(player_api, table)
    first = player_api.post(f"{table['url']}/instance/level-up/hp-roll").json()["level_up"]["hp"]["rolled"]
    again = player_api.post(f"{table['url']}/instance/level-up/hp-roll").json()["level_up"]["hp"]["rolled"]
    assert 1 <= first <= 10 and again == first
    body = level_up(player_api, table["url"], 2, hp_method="roll")
    con = next(a["modifier"] for a in body["sheet"]["abilities"] if a["key"] == "con")
    assert body["sheet"]["hit_point_levels"][1] == {"level": 2, "method": "roll", "die": first, "gain": max(1, first + con)}


def test_only_the_dms_hit_point_methods_are_allowed(table: dict, user_api: APIRequestContext,
                                                    player_api: APIRequestContext):
    bring(player_api, table)
    preview = player_api.get(f"{table['url']}/instance/level-up").json()["level_up"]
    refused = player_api.post(f"{table['url']}/instance/level-up", data={"build": preview["build"], "hp_method": "max"})
    assert refused.status == 400 and refused.json()["errors"]["hp_method"].startswith("Choose how to gain hit points")
    unrolled = player_api.post(f"{table['url']}/instance/level-up", data={"build": preview["build"], "hp_method": "roll"})
    assert unrolled.json()["errors"]["hp_method"] == "Roll your hit die first."

    set_rules(user_api, table, hp_methods=["max"])
    assert player_api.post(f"{table['url']}/instance/level-up/hp-roll").status == 400
    before = mine(player_api, table)["sheet"]["hit_points"]
    body = level_up(player_api, table["url"], 2, hp_method="max")
    con = next(a["modifier"] for a in body["sheet"]["abilities"] if a["key"] == "con")
    assert body["sheet"]["hit_points"] == before + 10 + con


# ------------------------------------------------------------------ locked picks
@pytest.mark.parametrize("change", [
    {"race": "dwarf", "subrace": "hill-dwarf"},
    {"class": "wizard"},
    {"background": None},
    {"ability_scores": {"method": "standard-array", "base": {"str": 8, "dex": 10, "con": 12, "int": 13, "wis": 14, "cha": 15}}},
    {"level": 2},
    {"items": {"bag-of-holding": 1}},
])
def test_who_the_character_is_is_locked(table: dict, player_api: APIRequestContext, change: dict):
    bring(player_api, table)
    build = mine(player_api, table)["instance"]["build"]
    response = player_api.patch(f"{table['url']}/instance", data={"build": {**build, **change}})
    assert response.status == 400, response.text()
    assert response.json()["error"] == "Earlier picks are locked in a campaign."


def test_earlier_choices_are_locked(table: dict, player_api: APIRequestContext):
    bring(player_api, table)
    build = mine(player_api, table)["instance"]["build"]
    skills = build["choices"]["class:proficiency-0"]
    other = next(o["value"] for o in next(s for s in mine(player_api, table)["slots"] if s["id"] == "class:proficiency-0")["options"]
                 if o["value"] not in skills and not o.get("denied"))
    changed = {**build, "choices": {**build["choices"], "class:proficiency-0": [skills[0], other]}}
    response = player_api.patch(f"{table['url']}/instance", data={"build": changed})
    assert response.status == 400
    assert response.json()["errors"][0]["field"] == "class:proficiency-0"


def test_name_notes_and_alignment_stay_editable(table: dict, player_api: APIRequestContext):
    bring(player_api, table)
    build = mine(player_api, table)["instance"]["build"]
    response = player_api.patch(f"{table['url']}/instance", data={"build": {
        **build, "name": "Aldric the Bold", "alignment": "chaotic-good", "notes": {"bond": "My sword is my oath."}}})
    assert response.ok, response.text()
    instance = response.json()["instance"]
    assert instance["name"] == "Aldric the Bold" and instance["build"]["notes"]["bond"] == "My sword is my oath."


def test_prepared_spells_change_any_time(table: dict, player_api: APIRequestContext):
    cleric = autofill(checker(player_api), blank(**{"class": "cleric", "subclass": "life"}))
    slot = next(s for s in checker(player_api)(cleric)["slots"] if s["id"] == "spells:prepared")
    options = slot["options"]
    prepared = [o["value"] for o in options if not o.get("denied")][:slot["choose"]]
    cleric["choices"]["spells:prepared"] = prepared
    bring(player_api, table, cleric, name="Sister Ama")
    detail = mine(player_api, table)
    swap = next(o["value"] for o in options if o["value"] not in prepared and not o.get("denied"))
    build = detail["instance"]["build"]
    response = player_api.patch(f"{table['url']}/instance", data={"build": {
        **build, "choices": {**build["choices"], "spells:prepared": [*prepared[1:], swap]}}})
    assert response.ok, response.text()


def test_a_level_up_cant_undo_earlier_picks(table: dict, player_api: APIRequestContext):
    wizard = autofill(checker(player_api), blank(**{"class": "wizard"}))
    bring(player_api, table, wizard, name="Elara")
    preview = player_api.get(f"{table['url']}/instance/level-up").json()["level_up"]
    book = preview["build"]["choices"]["spells:spellbook"]
    cantrips = preview["build"]["choices"]["spells:cantrips"]
    options = next(s for s in checker(player_api)(preview["build"])["slots"] if s["id"] == "spells:cantrips")["options"]
    other = next(o["value"] for o in options if o["value"] not in cantrips and not o.get("denied"))
    build = {**preview["build"], "subclass": "evocation",
             "choices": {**preview["build"]["choices"], "spells:cantrips": [*cantrips[1:], other]}}
    build = autofill(checker(player_api), build, {"spells:spellbook": book})
    response = player_api.post(f"{table['url']}/instance/level-up", data={"build": build, "hp_method": "average"})
    assert response.status == 400
    assert response.json()["errors"][0]["field"] == "spells:cantrips"


def test_a_known_caster_may_swap_one_spell_per_level(table: dict, player_api: APIRequestContext):
    sorcerer = autofill(checker(player_api), blank(**{"class": "sorcerer", "subclass": "draconic"}))
    bring(player_api, table, sorcerer, name="Vex")
    check = checker(player_api)

    def attempt(keep_from: int) -> int:
        """Level up keeping the known spells from index `keep_from` on, filling the rest with new ones."""
        preview = player_api.get(f"{table['url']}/instance/level-up").json()["level_up"]
        assert preview["swaps"] == {"spells:known": "known spell"}
        known = preview["build"]["choices"]["spells:known"]
        slot = next(s for s in check(preview["build"])["slots"] if s["id"] == "spells:known")
        new = [o["value"] for o in slot["options"] if not o.get("denied") and o["value"] not in known]
        kept = known[keep_from:]
        build = {**preview["build"], "choices": {**preview["build"]["choices"],
                                                 "spells:known": kept + new[:slot["choose"] - len(kept)]}}
        return player_api.post(f"{table['url']}/instance/level-up", data={"build": build, "hp_method": "average"}).status

    assert attempt(1) == 200   # level 2: one spell swapped, plus the new one
    assert attempt(2) == 400   # level 3: swapping two at once is refused


# ------------------------------------------------------------------ items
def test_only_the_dm_adds_items_and_the_player_uses_them_up(table: dict, user_api: APIRequestContext,
                                                           player_api: APIRequestContext):
    instance = bring(player_api, table)
    given = user_api.post(f"{instance['dm_url']}/items", data={"item": "potion-of-healing", "quantity": 2})
    assert given.status == 201 and given.json()["message"] == "You gave 2 × Potion of Healing to Aldric Vane."
    row = next(i for i in mine(player_api, table)["sheet"]["inventory"] if i["index"] == "potion-of-healing")
    assert (row["quantity"], row["given"]) == (2, 2)

    # The player drinks one
    build = mine(player_api, table)["instance"]["build"]
    drank = player_api.patch(f"{table['url']}/instance", data={"build": {**build, "used": {"potion-of-healing": 1}}})
    assert drank.ok, drank.text()
    assert next(i for i in drank.json()["sheet"]["inventory"] if i["index"] == "potion-of-healing")["quantity"] == 1
    # ...but can't give themselves more
    more = player_api.patch(f"{table['url']}/instance", data={"build": {**build, "given": {"potion-of-healing": 9}}})
    assert more.status == 400
    assert player_api.post(f"{instance['dm_url']}/items", data={"item": "potion-of-healing"}).status == 403

    # The DM takes the last one back
    taken = user_api.delete(f"{instance['dm_url']}/items/potion-of-healing?quantity=1")
    assert taken.ok
    assert not any(i["index"] == "potion-of-healing" for i in taken.json()["sheet"]["inventory"])
    assert user_api.post(f"{instance['dm_url']}/items", data={"item": "not-a-thing"}).status == 400


def test_dropping_starting_kit_and_wearing_it_off(table: dict, player_api: APIRequestContext):
    bring(player_api, table)
    detail = mine(player_api, table)
    armour = detail["sheet"]["equipped"]["armor"]
    build = detail["instance"]["build"]
    dropped = player_api.patch(f"{table['url']}/instance", data={"build": {**build, "used": {armour: 1}}})
    assert dropped.ok, dropped.text()
    assert dropped.json()["sheet"]["equipped"]["armor"] is None
    too_many = player_api.patch(f"{table['url']}/instance", data={"build": {**build, "used": {armour: 5}}})
    assert too_many.status == 400


# ------------------------------------------------------------------ spells
def test_a_granted_spell_is_known_by_non_wizards(table: dict, user_api: APIRequestContext, player_api: APIRequestContext):
    instance = bring(player_api, table)
    response = user_api.post(f"{instance['dm_url']}/spells", data={"spell": "misty-step"})
    assert response.status == 201 and response.json()["message"] == "Aldric Vane now knows Misty Step."
    spells = mine(player_api, table)["sheet"]["spellcasting"]["spells"]
    assert [(s["name"], s["source"]) for s in spells] == [("Misty Step", "Granted by your DM")]
    assert user_api.post(f"{instance['dm_url']}/spells", data={"spell": "misty-step"}).status == 409
    revoked = user_api.delete(f"{instance['dm_url']}/spells/misty-step")
    assert revoked.ok and revoked.json()["sheet"]["spellcasting"] is None


def test_a_wizard_copies_a_granted_spell_into_the_book(table: dict, user_api: APIRequestContext,
                                                       player_api: APIRequestContext):
    wizard = autofill(checker(player_api), blank(**{"class": "wizard"}))
    instance = bring(player_api, table, wizard, name="Elara")
    book = mine(player_api, table)["instance"]["build"]["choices"]["spells:spellbook"]
    spell = next(s for s in ("identify", "shield", "sleep", "thunderwave") if s not in book)
    assert user_api.post(f"{instance['dm_url']}/spells", data={"spell": "cure-wounds"}).status == 400   # not a wizard spell
    assert user_api.post(f"{instance['dm_url']}/spells", data={"spell": spell}).status == 201
    progress = mine(player_api, table)["instance"]["progress"]
    assert [(s["index"], s["copied"]) for s in progress["granted_spells"]] == [(spell, False)]

    copied = player_api.post(f"{table['url']}/instance/spellbook", data={"spell": spell})
    assert copied.ok, copied.text()
    spells = {s["index"]: s["source"] for s in copied.json()["sheet"]["spellcasting"]["spells"]}
    assert spells[spell] == "Copied into your spellbook"
    assert player_api.post(f"{table['url']}/instance/spellbook", data={"spell": "fireball"}).status == 400


# ------------------------------------------------------------------ DM overrides
def test_the_dm_raises_a_level_and_the_player_levels_up(table: dict, user_api: APIRequestContext,
                                                       player_api: APIRequestContext):
    set_rules(user_api, table, levelling="xp")
    instance = bring(player_api, table)
    response = user_api.put(f"{instance['dm_url']}/progress", data={"level": 3})
    assert response.ok and response.json()["message"] == "Aldric Vane can level up to level 3."
    progress = mine(player_api, table)["instance"]["progress"]
    assert (progress["levels_owed"], progress["xp"]) == (2, 900)
    body = level_up(player_api, table["url"], 3)
    assert body["instance"]["level"] == 3


def test_the_dm_sets_a_level_back(table: dict, user_api: APIRequestContext, player_api: APIRequestContext):
    instance = bring(player_api, table)
    user_api.post(f"{instance['dm_url']}/items", data={"item": "bag-of-holding"})
    level_up(player_api, table["url"], 3)
    back = user_api.put(f"{instance['dm_url']}/progress", data={"level": 2})
    assert back.ok, back.text()
    assert back.json()["instance"]["level"] == 2 and back.json()["instance"]["subclass"] is None
    assert back.json()["instance"]["build"]["given"] == {"bag-of-holding": 1}   # items stay
    too_low = user_api.put(f"{instance['dm_url']}/progress", data={"level": 1})
    assert too_low.ok   # level 1 is where Aldric joined
    assert user_api.put(f"{instance['dm_url']}/progress", data={"xp": 5000}).json()["instance"]["xp"] == 5000
    assert player_api.put(f"{instance['dm_url']}/progress", data={"level": 20}).status == 403


def test_the_dm_cant_go_below_the_level_a_character_joined_at(table: dict, user_api: APIRequestContext,
                                                              player_api: APIRequestContext):
    level3 = autofill(checker(player_api), {**aldric(), "level": 3, "subclass": "champion"})
    instance = bring(player_api, table, level3)
    response = user_api.put(f"{instance['dm_url']}/progress", data={"level": 2})
    assert response.status == 400
    assert "level 3 or higher" in response.json()["errors"]["level"]


# ------------------------------------------------------------------ warnings, not errors
def test_rule_bending_gear_is_flagged_not_refused(user_api: APIRequestContext):
    wizard = autofill(checker(user_api), blank(**{"class": "wizard", "ability_scores": {
        "method": "standard-array", "base": {"str": 8, "dex": 14, "con": 13, "int": 15, "wis": 12, "cha": 10}}}))
    attune = ["amulet-of-health", "amulet-of-the-planes", "armor-of-resistance", "animated-shield"]
    build = {**wizard, "items": {"chain-mail": 20, **{i: 1 for i in attune}}, "attuned": attune,
             "equipped": {"armor": "chain-mail", "shield": None}}
    result = user_api.post("/api/characters/check", data={"build": build}).json()
    assert result["valid"], result["errors"]
    codes = [w["code"] for w in result["sheet"]["warnings"]]
    assert codes == ["armor-proficiency", "armor-strength", "attunement", "encumbrance"]
    assert result["sheet"]["speed"] == 5
