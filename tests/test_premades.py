"""Premade characters must be legal level 1 builds made only from SRD rules data.

These run without the server or a browser: they read the premade JSON and the rules
snapshot directly, so a typo in an index or a broken rule fails fast in CI.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PREMADES = sorted((ROOT / "backend" / "tof" / "premades").glob("*.json"))
RULES = ROOT / "backend" / "tof" / "rules" / "data"
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]


def rules(kind: str) -> dict[str, dict]:
    return {e["index"]: e for e in json.loads((RULES / f"5e-SRD-{kind}.json").read_text(encoding="utf-8"))}


def option_indexes(choice: dict) -> set[str]:
    return {o["item"]["index"] for o in choice["from"]["options"]}


def mod(score: int) -> int:
    return (score - 10) // 2


def final_scores(pc: dict) -> dict[str, int]:
    race = rules("Races")[pc["race"]]
    scores = dict(pc["ability_scores"]["base"])
    for bonus in race["ability_bonuses"]:
        scores[bonus["ability_score"]["index"]] += bonus["bonus"]
    return scores


@pytest.fixture(params=PREMADES, ids=[p.stem for p in PREMADES])
def pc(request) -> dict:
    return json.loads(request.param.read_text(encoding="utf-8"))


def test_there_is_at_least_one_premade():
    assert PREMADES


def test_core_choices_exist_in_the_srd(pc):
    assert pc["race"] in rules("Races")
    assert pc["class"] in rules("Classes")
    assert pc["background"] in rules("Backgrounds")
    assert pc["alignment"] in rules("Alignments")
    assert pc["level"] == 1


def test_ability_scores_use_the_standard_array(pc):
    assert pc["ability_scores"]["method"] == "standard-array"
    assert sorted(pc["ability_scores"]["base"].values(), reverse=True) == STANDARD_ARRAY


def test_skills_and_languages_are_legal(pc):
    cls = rules("Classes")[pc["class"]]
    skill_choice = cls["proficiency_choices"][0]
    picked = pc["choices"]["class_skills"]
    assert len(picked) == skill_choice["choose"]
    assert set(picked) <= option_indexes(skill_choice)

    race = rules("Races")[pc["race"]]
    background = rules("Backgrounds")[pc["background"]]
    languages = rules("Languages")
    if "language_options" in race:
        assert len(pc["choices"]["race_languages"]) == race["language_options"]["choose"]
        assert set(pc["choices"]["race_languages"]) <= option_indexes(race["language_options"])
    assert len(pc["choices"]["background_languages"]) == background["language_options"]["choose"]
    known = [l["index"] for l in race["languages"]] + pc["choices"]["race_languages"] + pc["choices"]["background_languages"]
    assert set(known) <= set(languages)
    assert len(known) == len(set(known)), "no language picked twice"


def test_fighting_style_is_a_level_1_class_feature(pc):
    style = pc["choices"].get("fighting_style")
    if style is None:
        pytest.skip("class has no fighting style")
    feature = rules("Features")[style]
    assert feature["class"]["index"] == pc["class"]
    assert feature["level"] == 1


def test_equipment_exists_and_equipped_items_are_owned(pc):
    equipment = rules("Equipment")
    owned = {i["index"] for c in pc["choices"]["starting_equipment"] for i in c["items"]}
    assert owned <= set(equipment)
    assert set(pc["equipped"].values()) <= owned


def test_human_fighter_derived_stats():
    pc = json.loads((ROOT / "backend" / "tof" / "premades" / "human-fighter.json").read_text(encoding="utf-8"))
    scores = final_scores(pc)
    equipment = rules("Equipment")
    armor = equipment[pc["equipped"]["armor"]]

    assert scores == {"str": 16, "dex": 14, "con": 15, "int": 9, "wis": 13, "cha": 11}
    assert scores["str"] >= armor["str_minimum"], "strong enough for chain mail"
    hit_points = rules("Classes")["fighter"]["hit_die"] + mod(scores["con"])
    armor_class = armor["armor_class"]["base"] + equipment[pc["equipped"]["shield"]]["armor_class"]["base"]
    assert hit_points == 12
    assert armor_class == 18
