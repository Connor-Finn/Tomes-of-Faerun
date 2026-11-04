"""The character rules engine, tested directly (no server, no browser).

The engine decides what a character may pick. The builder only shows its answers, so this is
where the D&D rules are covered in depth: one test per rule.
"""
import pytest

from builds import aldric, autofill, blank
from rules_engine import engine


def check(build: dict, **kwargs) -> dict:
    return engine.check(build, **kwargs)


def slot(result: dict, slot_id: str) -> dict:
    return next(s for s in result["slots"] if s["id"] == slot_id)


def denied(result: dict, slot_id: str) -> dict[str, str]:
    return {o["value"]: o["denied"] for o in slot(result, slot_id)["options"] if o.get("denied")}


def messages(result: dict) -> str:
    return " | ".join(e["message"] for e in result["errors"])


# ------------------------------------------------------------------ drafts and completeness
def test_an_empty_build_is_a_valid_draft():
    result = check({})
    assert result["valid"]
    assert not result["complete"]
    fields = {m["field"] for m in result["missing"]}
    assert {"name", "race", "class", "background", "alignment", "ability_scores"} <= fields


def test_every_class_and_race_can_be_finished_at_level_1_and_20():
    for cls in ("barbarian", "bard", "cleric", "druid", "fighter", "monk",
                "paladin", "ranger", "rogue", "sorcerer", "warlock", "wizard"):
        for level in (1, 20):
            subclass = engine.rules.get("classes", cls)["subclasses"][0]["index"] if level >= engine.subclass_level(cls) else None
            build = autofill(check, blank(**{"class": cls, "level": level, "subclass": subclass, "race": "half-elf"}))
            assert check(build)["complete"], (cls, level)


# ------------------------------------------------------------------ core picks
@pytest.mark.parametrize("field,value", [("race", "orc"), ("class", "artificer"), ("background", "noble"),
                                         ("alignment", "chaotic-great")])
def test_unknown_rules_entries_are_refused(field, value):
    result = check(blank(**{field: value}))
    assert not result["valid"]
    assert result["errors"][0]["field"] == field


@pytest.mark.parametrize("level", [0, 21, "3", 2.5])
def test_level_must_be_1_to_20(level):
    assert not check(blank(level=level))["valid"]


def test_multiclassing_is_refused():
    result = check(blank(classes=[{"class": "fighter", "level": 1}, {"class": "wizard", "level": 1}]))
    assert "Multiclassing isn't available" in messages(result)


def test_subrace_must_belong_to_the_race():
    assert check(blank(race="dwarf", subrace="hill-dwarf"))["valid"]
    assert not check(blank(race="dwarf", subrace="high-elf"))["valid"]
    assert any(m["field"] == "subrace" for m in check(blank(race="dwarf"))["missing"])


def test_subclass_is_needed_from_the_class_subclass_level():
    assert engine.subclass_level("fighter") == 3
    assert engine.subclass_level("cleric") == 1
    assert not any(m["field"] == "subclass" for m in check(blank(level=2))["missing"])
    assert any(m["field"] == "subclass" for m in check(blank(level=3))["missing"])
    assert not check(blank(level=3, subclass="evocation"))["valid"]   # a wizard subclass


def test_lowering_the_level_drops_a_subclass_picked_too_early():
    cleaned = engine.clean(blank(level=2, subclass="champion"))
    assert cleaned["subclass"] is None


# ------------------------------------------------------------------ ability scores
def test_standard_array_must_use_each_number_once():
    build = blank(ability_scores={"method": "standard-array",
                                  "base": {"str": 15, "dex": 15, "con": 13, "int": 12, "wis": 10, "cha": 8}})
    assert "standard array" in messages(check(build))


def test_point_buy_has_a_budget_of_27():
    fine = {"str": 15, "dex": 15, "con": 15, "int": 8, "wis": 8, "cha": 8}   # 27 points
    too_much = {**fine, "int": 9}                                         # 28 points
    too_high = {**fine, "str": 16}
    assert check(blank(ability_scores={"method": "point-buy", "base": fine}))["valid"]
    assert "costs 28 points" in messages(check(blank(ability_scores={"method": "point-buy", "base": too_much})))
    assert "between 8 and 15" in messages(check(blank(ability_scores={"method": "point-buy", "base": too_high})))


def test_rolled_scores_are_not_accepted():
    assert not check(blank(ability_scores={"method": "rolled", "base": {a: 18 for a in engine.ABILITIES}}))["valid"]


def test_racial_bonuses_are_added():
    scores = {a["key"]: a for a in check(blank(race="dwarf", subrace="hill-dwarf"))["sheet"]["abilities"]}
    assert scores["con"]["score"] == 15 and scores["con"]["bonus"] == 2
    assert scores["wis"]["score"] == 11 and scores["wis"]["bonus"] == 1


def test_half_elf_picks_two_different_abilities_but_not_charisma():
    build = blank(race="half-elf", choices={"race:ability-bonus": ["str", "dex"]})
    scores = {a["key"]: a["score"] for a in check(build)["sheet"]["abilities"]}
    assert scores["str"] == 16 and scores["dex"] == 15 and scores["cha"] == 10
    assert not check(blank(race="half-elf", choices={"race:ability-bonus": ["cha", "dex"]}))["valid"]
    assert not check(blank(race="half-elf", choices={"race:ability-bonus": ["str", "str"]}))["valid"]


# ------------------------------------------------------------------ skills and languages
def test_class_skills_come_from_the_class_list():
    assert not check(blank(choices={"class:proficiency-0": ["skill-arcana", "skill-athletics"]}))["valid"]


def test_a_pick_that_isnt_an_option_is_named_in_plain_words():
    result = check(blank(choices={"class:proficiency-0": ["skill-arcana", "skill-athletics"]}))
    assert "Arcana isn't one of the options" in messages(result)
    assert "skill-arcana" not in messages(result)


def test_a_skill_from_your_background_cant_be_picked_again():
    # Acolytes already know Insight and Religion
    result = check(blank(**{"class": "cleric"}))
    assert "already proficient" in denied(result, "class:proficiency-0")["skill-insight"]
    assert not check(blank(**{"class": "cleric", "choices": {"class:proficiency-0": ["skill-insight", "skill-history"]}}))["valid"]


def test_too_many_picks_are_refused():
    result = check(blank(choices={"class:proficiency-0": ["skill-athletics", "skill-perception", "skill-survival"]}))
    assert "Pick at most 2" in messages(result)


def test_languages_you_already_speak_are_denied():
    result = check(blank())
    assert "You already speak it" in denied(result, "background:languages")["common"]
    assert not check(blank(choices={"background:languages": ["common", "elvish"]}))["valid"]


def test_the_same_language_cant_come_from_two_places():
    build = blank(choices={"race:languages": ["elvish"], "background:languages": ["elvish", "dwarvish"]})
    assert "You already speak it" in messages(check(build))


# ------------------------------------------------------------------ class features
def test_fighting_style_options_come_from_the_class():
    result = check(blank())
    values = {o["value"] for o in slot(result, "feature:fighter-fighting-style")["options"]}
    assert "fighter-fighting-style-dueling" in values
    assert "ranger-fighting-style-archery" not in values


def test_expertise_needs_proficiency():
    build = autofill(check, blank(**{"class": "rogue"}), prefer={"class:proficiency-0": ["skill-stealth"]})
    result = check(build)
    expertise = denied(result, "feature:rogue-expertise-1")
    assert "skill-stealth" not in expertise
    assert "skill-arcana" in expertise and "proficient" in expertise["skill-arcana"]


def test_ability_score_improvement_caps_scores_at_20():
    build = autofill(check, blank(level=4, subclass="champion", ability_scores={
        "method": "point-buy", "base": {"str": 15, "dex": 15, "con": 15, "int": 8, "wis": 8, "cha": 8}}))
    build["choices"]["asi:fighter-ability-score-improvement-1"] = ["str", "str"]
    assert check(build)["valid"]   # human 16 + 2 = 18
    build["choices"]["asi:fighter-ability-score-improvement-1"] = ["str", "str", "dex"]
    assert not check(build)["valid"]


def test_feats_check_their_prerequisites():
    weak = blank(level=4, ability_scores={"method": "standard-array",
                                          "base": {"str": 8, "dex": 15, "con": 14, "int": 13, "wis": 12, "cha": 10}},
                 race="elf", subrace="high-elf")
    result = check(weak)
    assert "Needs Strength 13" in denied(result, "asi:fighter-ability-score-improvement-1")["feat:grappler"]
    weak["choices"]["asi:fighter-ability-score-improvement-1"] = ["feat:grappler"]
    assert not check(weak)["valid"]
    strong = blank(level=4, choices={"asi:fighter-ability-score-improvement-1": ["feat:grappler"]})
    assert check(strong)["valid"]
    assert any(f["name"] == "Grappler" for f in check(strong)["sheet"]["features"])


def test_eldritch_invocations_check_prerequisites():
    build = blank(**{"class": "warlock", "subclass": "fiend", "level": 2})
    result = check(build)
    agonizing = denied(result, "feature:eldritch-invocations")["eldritch-invocation-agonizing-blast"]
    assert "Eldritch Blast" in agonizing
    assert "level 5" in denied(result, "feature:eldritch-invocations")["eldritch-invocation-thirsting-blade"]
    build["choices"]["spells:cantrips"] = ["eldritch-blast", "minor-illusion"]
    assert "eldritch-invocation-agonizing-blast" not in denied(check(build), "feature:eldritch-invocations")


# ------------------------------------------------------------------ spells
def test_spells_must_be_on_the_class_list_and_castable():
    result = check(blank(**{"class": "wizard"}))
    book = denied(result, "spells:spellbook")
    assert "class's spell list" in book["cure-wounds"]
    assert "level 2" in book["misty-step"]
    assert "magic-missile" not in book


def test_wizards_prepare_from_their_spellbook():
    build = autofill(check, blank(**{"class": "wizard", "ability_scores": {
        "method": "standard-array", "base": {"str": 8, "dex": 14, "con": 13, "int": 15, "wis": 12, "cha": 10}}}),
        prefer={"spells:spellbook": ["magic-missile", "shield", "sleep", "mage-armor", "detect-magic", "find-familiar"]})
    result = check(build)
    prepared = slot(result, "spells:prepared")
    assert prepared["choose"] == 4                      # INT 16 (+3) + level 1
    assert "spellbook" in denied(result, "spells:prepared")["burning-hands"]
    build["choices"]["spells:prepared"] = ["magic-missile", "shield", "sleep"]
    sheet = check(build)["sheet"]["spellcasting"]
    assert sheet["save_dc"] == 13 and sheet["attack_bonus"] == 5
    assert {s["index"] for s in sheet["spells"] if s["prepared"] and s["level"] == 1} == {"magic-missile", "shield", "sleep"}


def test_paladins_cast_from_level_2():
    assert not any(s["group"] == "spells" for s in check(blank(**{"class": "paladin"}))["slots"])
    assert any(s["id"] == "spells:prepared" for s in check(blank(**{"class": "paladin", "level": 2}))["slots"])


def test_domain_spells_are_added_automatically():
    sheet = check(blank(**{"class": "cleric", "subclass": "life"}))["sheet"]
    names = {s["name"]: s["source"] for s in sheet["spellcasting"]["spells"]}
    assert names["Bless"] == "Life" and names["Cure Wounds"] == "Life"


def test_high_elves_pick_a_wizard_cantrip():
    result = check(blank(race="elf", subrace="high-elf"))
    values = {o["value"] for o in slot(result, "trait:high-elf-cantrip")["options"]}
    assert "fire-bolt" in values and "sacred-flame" not in values


# ------------------------------------------------------------------ equipment and the sheet
def test_equipment_choices_fill_the_inventory():
    result = check(aldric())
    inventory = {i["index"]: i["quantity"] for i in result["sheet"]["inventory"]}
    assert inventory["chain-mail"] == 1 and inventory["crossbow-bolt"] == 20 and inventory["emblem"] == 1


def test_only_owned_armour_counts():
    build = aldric()
    build["equipped"] = {"armor": "plate-armor", "shield": "shield"}
    cleaned = engine.clean(build)
    assert cleaned["equipped"]["armor"] is None
    assert check(cleaned)["sheet"]["armor_class"] == 14   # 10 + DEX 2 + shield 2


def test_unarmored_defense():
    build = blank(**{"class": "barbarian", "equipped": {"armor": None, "shield": None}})
    sheet = check(build)["sheet"]
    assert sheet["armor_class"] == 10 + 2 + 2     # human DEX 15 -> +2, CON 14 -> +2
    assert sheet["armor_class_note"] == "Unarmored Defense"


def test_hit_points_use_the_average_after_level_1():
    sheet = check(blank(level=5, race="dwarf", subrace="hill-dwarf"))["sheet"]
    # CON 13 + 2 = 15 (+2). Level 1: 10 + 2. Levels 2-5: 4 x (6 + 2). Dwarven Toughness: +5.
    assert sheet["hit_points"] == 12 + 32 + 5


# ------------------------------------------------------------------ clean-up and build modes
def test_changing_class_drops_the_old_class_choices():
    build = aldric()
    build["class"] = "wizard"
    cleaned = engine.clean(build)
    assert "feature:fighter-fighting-style" not in cleaned["choices"]
    assert cleaned["choices"]["race:languages"] == ["dwarvish"]


def test_easy_build_creates_characters_up_to_level_3():
    assert check(blank(level=3), build_mode="easy")["valid"]
    result = check(blank(level=4), build_mode="easy")
    assert "Easy build creates characters up to level 3" in messages(result)
    assert check(blank(level=4), build_mode="standard")["valid"]
    # A character that is already higher can still switch to Easy build
    assert check(blank(level=8), build_mode="easy", previous_level=8)["valid"]


def test_best_armour_is_worn_until_the_player_says_otherwise():
    build = aldric()
    del build["equipped"]
    sheet = check(build)["sheet"]
    assert sheet["equipped"] == {"armor": "chain-mail", "shield": "shield"}
    assert sheet["armor_class"] == 18
    build["equipped"] = {"armor": None, "shield": None}
    assert check(build)["sheet"]["armor_class"] == 12   # unarmoured: 10 + DEX 2
