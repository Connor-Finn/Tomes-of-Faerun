"""D&D 5e rules content (System Reference Document 5.1).

The data in `data/` is a snapshot of the 5e-bits/5e-database project, the same
data the free D&D 5e API (https://www.dnd5eapi.co) serves. It is loaded into
memory once: it is read-only and small (a few MB), so filtering it in Python is
faster and simpler than a database round trip. Users' own data (characters,
spellbooks, monster collections) lives in the database and refers to rules
entries by their `index` slug, e.g. "fireball" or "adult-red-dragon".

Refresh the snapshot with `python backend/scripts/sync_rules.py`.
"""
from __future__ import annotations

import json
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
UPSTREAM_IMAGE_HOST = "https://www.dnd5eapi.co"

# URL slug -> data file name. The slugs match the 5e API's endpoints.
KINDS: dict[str, str] = {
    "ability-scores": "Ability-Scores",
    "alignments": "Alignments",
    "backgrounds": "Backgrounds",
    "classes": "Classes",
    "conditions": "Conditions",
    "damage-types": "Damage-Types",
    "equipment": "Equipment",
    "equipment-categories": "Equipment-Categories",
    "feats": "Feats",
    "features": "Features",
    "languages": "Languages",
    "levels": "Levels",
    "magic-items": "Magic-Items",
    "magic-schools": "Magic-Schools",
    "monsters": "Monsters",
    "proficiencies": "Proficiencies",
    "races": "Races",
    "rule-sections": "Rule-Sections",
    "rules": "Rules",
    "skills": "Skills",
    "spells": "Spells",
    "subclasses": "Subclasses",
    "subraces": "Subraces",
    "traits": "Traits",
    "weapon-properties": "Weapon-Properties",
}


def _rewrite_urls(node: Any) -> Any:
    """Point the upstream API's links (/api/2014/spells/x) at our own API (/api/rules/spells/x)."""
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == "url" and isinstance(value, str) and value.startswith("/api/2014/"):
                out[key] = "/api/rules/" + value[len("/api/2014/"):]
            elif key == "image" and isinstance(value, str) and value.startswith("/api/images/"):
                out[key] = UPSTREAM_IMAGE_HOST + value
            else:
                out[key] = _rewrite_urls(value)
        return out
    if isinstance(node, list):
        return [_rewrite_urls(v) for v in node]
    return node


@lru_cache(maxsize=None)
def load(kind: str) -> tuple[dict, ...]:
    """All entries of one kind, sorted by name. Cached for the life of the process."""
    entries = json.loads((DATA_DIR / f"5e-SRD-{KINDS[kind]}.json").read_text(encoding="utf-8"))
    entries = [_rewrite_urls(e) for e in entries]
    if kind == "levels":
        entries.sort(key=lambda e: (e.get("class", {}).get("index", ""), e.get("subclass", {}).get("index", ""), e["level"]))
    else:
        entries.sort(key=lambda e: e["name"].lower())
    return tuple(entries)


@lru_cache(maxsize=None)
def by_index(kind: str) -> dict[str, dict]:
    return {e["index"]: e for e in load(kind)}


def get(kind: str, index: str) -> dict | None:
    return by_index(kind).get(index)


def cr_label(cr: float) -> str:
    """0.125 -> "1/8", 2 -> "2"."""
    return str(Fraction(cr).limit_denominator(8))
