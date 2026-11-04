"""Premade characters must be complete, legal builds made only from SRD rules data.

These run the rules engine directly (no server or browser), so a typo in an index or a
broken rule in a premade fails fast in CI.
"""
import json

import pytest

from builds import PREMADES
from rules_engine import engine

FILES = sorted(PREMADES.glob("*.json"))


@pytest.fixture(params=FILES, ids=[p.stem for p in FILES])
def premade(request) -> dict:
    return json.loads(request.param.read_text(encoding="utf-8"))


def test_there_is_at_least_one_premade():
    assert FILES


def test_premade_is_a_complete_legal_build(premade):
    result = engine.check(premade["build"], build_mode=premade.get("build_mode", "standard"),
                          previous_level=premade["build"]["level"])
    assert result["errors"] == []
    assert result["missing"] == []
    assert result["complete"]


def test_premade_id_matches_its_file_name(premade):
    assert (PREMADES / f"{premade['id']}.json").is_file()


def test_premade_has_a_summary_and_notes(premade):
    assert premade["summary"]
    assert premade["build"]["name"]
    assert premade["build"]["notes"]["backstory"]


def test_human_fighter_sheet():
    build = json.loads((PREMADES / "human-fighter.json").read_text(encoding="utf-8"))["build"]
    sheet = engine.check(build)["sheet"]
    scores = {a["key"]: a["score"] for a in sheet["abilities"]}
    assert scores == {"str": 16, "dex": 14, "con": 15, "int": 9, "wis": 13, "cha": 11}
    assert sheet["hit_points"] == 12                 # d10 + CON 2
    assert sheet["armor_class"] == 18                # chain mail 16 + shield 2
    assert sheet["proficiency_bonus"] == 2
    assert sheet["passive_perception"] == 13         # 10 + WIS 1 + proficiency 2
    longsword = next(a for a in sheet["attacks"] if a["index"] == "longsword")
    assert longsword["attack_bonus"] == 5            # STR 3 + proficiency 2
    assert longsword["damage"] == "1d8 + 5"          # STR 3 + Dueling 2
