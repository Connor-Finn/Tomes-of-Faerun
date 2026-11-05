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


SUBCLASS_AT = {"fighter": (3, "champion"), "wizard": (2, "evocation"), "cleric": (1, "life")}


def level_up(ctx, campaign_url: str, to_level: int | None = None, prefer: dict[str, list[str]] | None = None,
             hp_method: str = "average", headers: dict | None = None) -> dict:
    """Level a campaign character up the way the guided Level Up does, one level at a time.

    Each level starts from what the app offers (GET .../instance/level-up), makes the open picks
    with autofill (and the SRD's subclass when it unlocks), then takes the level.
    """
    def check(build: dict) -> dict:
        response = ctx.post("/api/characters/check", data={"build": build, "previous_level": 20}, headers=headers)
        assert response.ok, response.text()
        return response.json()

    body = {}
    current = ctx.get(f"{campaign_url}/instance").json()["instance"]["level"]
    for _ in range((to_level or current + 1) - current):
        preview = ctx.get(f"{campaign_url}/instance/level-up").json()["level_up"]
        assert preview["allowed"], preview["reason"]
        build = preview["build"]
        level, subclass = SUBCLASS_AT.get(build["class"], (3, None))
        if preview["subclass_unlocks"] and subclass:
            build = {**build, "subclass": subclass}
        if hp_method == "roll":
            ctx.post(f"{campaign_url}/instance/level-up/hp-roll", headers=headers)
        # Keep the picks already made (earlier picks are locked), then the preferred ones
        keep = {k: list(v) + list((prefer or {}).get(k, [])) for k, v in (build.get("choices") or {}).items()}
        build = autofill(check, build, {**(prefer or {}), **keep})
        response = ctx.post(f"{campaign_url}/instance/level-up", data={"build": build, "hp_method": hp_method},
                            headers=headers)
        assert response.ok, response.text()
        body = response.json()
    return body
