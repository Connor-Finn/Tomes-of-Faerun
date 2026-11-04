"""Character builds for tests, and a helper that finishes a build the way a player would.

`autofill` asks the rules engine (through any `check` function: the engine itself or the
/api/characters/check endpoint) which choices are still open, and picks the first options
the rules allow, until the build is complete.
"""
from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREMADES = ROOT / "backend" / "tof" / "premades"


def premade(template_id: str = "human-fighter") -> dict:
    return json.loads((PREMADES / f"{template_id}.json").read_text(encoding="utf-8"))


def aldric() -> dict:
    """Aldric Vane, the level 1 human fighter premade."""
    return premade("human-fighter")["build"]


def blank(**overrides) -> dict:
    build = {
        "name": "Test Hero", "level": 1, "race": "human", "subrace": None, "class": "fighter", "subclass": None,
        "background": "acolyte", "alignment": "neutral",
        "ability_scores": {"method": "standard-array",
                           "base": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8}},
        "choices": {},
    }
    build.update(overrides)
    return build


def autofill(check: Callable[[dict], dict], build: dict, prefer: dict[str, list[str]] | None = None) -> dict:
    """Fill every open choice with the first allowed options. Returns the finished build."""
    build = copy.deepcopy(build)
    build.setdefault("choices", {})
    prefer = prefer or {}
    for _ in range(100):
        result = check(build)
        open_slot = next((s for s in result["slots"] if not s["complete"]), None)
        if open_slot is None:
            assert result["complete"], result["missing"]
            return build
        if open_slot["kind"] == "asi":
            lowest = min(result["sheet"]["abilities"], key=lambda a: a["score"])["key"]
            build["choices"][open_slot["id"]] = [lowest, lowest]
            continue
        allowed = [o["value"] for o in open_slot["options"] if not o.get("denied")]
        wanted = [v for v in prefer.get(open_slot["id"], []) if v in allowed]
        build["choices"][open_slot["id"]] = (wanted + [v for v in allowed if v not in wanted])[:open_slot["choose"]]
    raise AssertionError("autofill didn't finish the build")
