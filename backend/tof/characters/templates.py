"""Premade characters players can start from (backend/tof/premades/*.json).

Each file holds a complete, legal build plus a short summary. Picking one copies its build into
a new character the player owns; later edits never touch the template.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import engine

PREMADE_DIR = Path(__file__).resolve().parent.parent / "premades"


@lru_cache(maxsize=None)
def premades() -> dict[str, dict]:
    out = {}
    for path in sorted(PREMADE_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[data["id"]] = data
    return out


def get(template_id: str) -> dict | None:
    return premades().get(template_id)


def summary(template: dict) -> dict:
    sheet = engine.sheet(engine.analyse(template["build"]))
    s = sheet["summary"]
    return {
        "id": template["id"],
        "name": s["name"],
        "summary": template.get("summary", ""),
        "level": s["level"],
        "race": s["subrace"] or s["race"],
        "class": s["class"],
        "background": s["background"],
        "build_mode": template.get("build_mode", "standard"),
        "hit_points": sheet["hit_points"],
        "armor_class": sheet["armor_class"],
    }
