"""Read-only endpoints for rules content: /api/rules/<kind>[/<index>].

Every list endpoint takes `q` (name search), `page` and `per_page`. The main
catalogues (spells, monsters, equipment, magic items) also take filters and
return `facets`: the values you can filter by, for building dropdowns.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Iterable

from flask import Blueprint, abort, jsonify, request

from . import KINDS, cr_label, get, load

bp = Blueprint("rules", __name__, url_prefix="/api/rules")

DEFAULT_PER_PAGE = 50
MAX_PER_PAGE = 500


# ---------------------------------------------------------------------------
# Summaries: the fields a list/table needs, so lists stay small.
# ---------------------------------------------------------------------------
def _names(refs: Iterable[dict]) -> list[str]:
    return [r["name"] for r in refs]


def spell_summary(s: dict) -> dict:
    return {
        "index": s["index"], "name": s["name"], "level": s["level"], "school": s["school"]["name"],
        "classes": _names(s.get("classes", [])), "casting_time": s["casting_time"], "range": s["range"],
        "duration": s["duration"], "components": s.get("components", []),
        "concentration": s.get("concentration", False), "ritual": s.get("ritual", False),
    }


def monster_summary(m: dict) -> dict:
    ac = m.get("armor_class") or [{}]
    return {
        "index": m["index"], "name": m["name"], "size": m["size"], "type": m["type"],
        "alignment": m.get("alignment", ""), "challenge_rating": m["challenge_rating"],
        "cr": cr_label(m["challenge_rating"]), "xp": m.get("xp", 0), "hit_points": m["hit_points"],
        "armor_class": ac[0].get("value"), "image": m.get("image"),
    }


def equipment_summary(e: dict) -> dict:
    cost = e.get("cost") or {}
    return {
        "index": e["index"], "name": e["name"], "category": e["equipment_category"]["name"],
        "category_index": e["equipment_category"]["index"],
        "subcategory": e.get("category_range") or e.get("armor_category") or (e.get("gear_category") or {}).get("name")
        or e.get("tool_category") or e.get("vehicle_category"),
        "cost": f"{cost['quantity']} {cost['unit']}" if cost else None, "weight": e.get("weight"),
    }


def magic_item_summary(i: dict) -> dict:
    return {
        "index": i["index"], "name": i["name"], "category": i["equipment_category"]["name"],
        "rarity": i["rarity"]["name"], "variant": i.get("variant", False),
        "variants": _names(i.get("variants", [])),
    }


def basic_summary(e: dict) -> dict:
    return {"index": e["index"], "name": e.get("name", e["index"])}


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
Filter = Callable[[dict], bool]


def _arg_bool(name: str) -> bool | None:
    value = request.args.get(name)
    if value is None or value == "":
        return None
    return value.lower() in ("1", "true", "yes")


def _arg_float(name: str) -> float | None:
    value = request.args.get(name, "").strip()
    if not value:
        return None
    try:
        if "/" in value:
            num, den = value.split("/")
            return int(num) / int(den)
        return float(value)
    except (ValueError, ZeroDivisionError):
        abort(400, description=f"'{name}' must be a number like 2 or 1/4.")


def _arg_list(name: str) -> list[str]:
    """?level=1&level=2 or ?level=1,2"""
    values: list[str] = []
    for raw in request.args.getlist(name):
        values += [v.strip().lower() for v in raw.split(",") if v.strip()]
    return values


def spell_filters() -> list[Filter]:
    filters: list[Filter] = []
    if levels := _arg_list("level"):
        filters.append(lambda s: str(s["level"]) in levels)
    if schools := _arg_list("school"):
        filters.append(lambda s: s["school"]["index"] in schools)
    if classes := _arg_list("class"):
        filters.append(lambda s: any(c["index"] in classes for c in s.get("classes", [])))
    if (ritual := _arg_bool("ritual")) is not None:
        filters.append(lambda s: s.get("ritual", False) == ritual)
    if (conc := _arg_bool("concentration")) is not None:
        filters.append(lambda s: s.get("concentration", False) == conc)
    return filters


def monster_filters() -> list[Filter]:
    filters: list[Filter] = []
    if types := _arg_list("type"):
        filters.append(lambda m: m["type"].lower() in types)
    if sizes := _arg_list("size"):
        filters.append(lambda m: m["size"].lower() in sizes)
    if (lo := _arg_float("cr_min")) is not None:
        filters.append(lambda m: m["challenge_rating"] >= lo)
    if (hi := _arg_float("cr_max")) is not None:
        filters.append(lambda m: m["challenge_rating"] <= hi)
    return filters


def equipment_filters() -> list[Filter]:
    filters: list[Filter] = []
    if cats := _arg_list("category"):
        filters.append(lambda e: e["equipment_category"]["index"] in cats)
    return filters


def magic_item_filters() -> list[Filter]:
    filters: list[Filter] = []
    if rarities := _arg_list("rarity"):
        filters.append(lambda i: i["rarity"]["name"].lower() in rarities)
    if cats := _arg_list("category"):
        filters.append(lambda i: i["equipment_category"]["index"] in cats)
    if not _arg_bool("include_variants"):
        # "Armor, +1, +2, or +3" is listed once; its variants show on its page.
        filters.append(lambda i: not i.get("variant", False))
    return filters


# ---------------------------------------------------------------------------
# Facets: the values available to filter by.
# ---------------------------------------------------------------------------
def _options(pairs: Iterable[tuple[str, str]]) -> list[dict]:
    return [{"value": v, "label": label} for v, label in sorted(set(pairs), key=lambda p: p[1])]


def spell_facets() -> dict:
    spells = load("spells")
    return {
        "level": [{"value": str(n), "label": "Cantrip" if n == 0 else f"Level {n}"}
                  for n in sorted({s["level"] for s in spells})],
        "school": _options((s["school"]["index"], s["school"]["name"]) for s in spells),
        "class": _options((c["index"], c["name"]) for s in spells for c in s.get("classes", [])),
    }


def monster_facets() -> dict:
    monsters = load("monsters")
    sizes = ["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"]
    crs = sorted({m["challenge_rating"] for m in monsters})
    return {
        "type": _options((m["type"].lower(), m["type"].capitalize()) for m in monsters),
        "size": [{"value": s.lower(), "label": s} for s in sizes if any(m["size"] == s for m in monsters)],
        "cr": [{"value": cr_label(cr), "label": cr_label(cr)} for cr in crs],
    }


def equipment_facets() -> dict:
    return {"category": _options((e["equipment_category"]["index"], e["equipment_category"]["name"])
                                 for e in load("equipment"))}


def magic_item_facets() -> dict:
    order = ["Common", "Uncommon", "Rare", "Very Rare", "Legendary", "Artifact", "Varies"]
    present = {i["rarity"]["name"] for i in load("magic-items")}
    return {
        "rarity": [{"value": r.lower(), "label": r} for r in order if r in present],
        "category": _options((i["equipment_category"]["index"], i["equipment_category"]["name"])
                             for i in load("magic-items")),
    }


CATALOGUES = {
    "spells": (spell_summary, spell_filters, spell_facets),
    "monsters": (monster_summary, monster_filters, monster_facets),
    "equipment": (equipment_summary, equipment_filters, equipment_facets),
    "magic-items": (magic_item_summary, magic_item_filters, magic_item_facets),
}

SORTS: dict[str, dict[str, Callable[[dict], object]]] = {
    "spells": {"name": lambda s: s["name"].lower(), "level": lambda s: (s["level"], s["name"].lower())},
    "monsters": {"name": lambda m: m["name"].lower(), "cr": lambda m: (m["challenge_rating"], m["name"].lower())},
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@bp.get("")
def index():
    return jsonify(kinds=[{"kind": k, "count": len(load(k)), "url": f"/api/rules/{k}"} for k in KINDS])


@bp.get("/<kind>")
def list_entries(kind: str):
    if kind not in KINDS:
        abort(404, description=f"Unknown rules category '{kind}'.")
    summarise, make_filters, facets = CATALOGUES.get(kind, (basic_summary, lambda: [], None))

    entries: Iterable[dict] = load(kind)
    if q := request.args.get("q", "").strip().lower():
        entries = [e for e in entries if q in e.get("name", e["index"]).lower()]
    for keep in make_filters():
        entries = [e for e in entries if keep(e)]
    entries = list(entries)

    sort = request.args.get("sort", "name")
    if sort in SORTS.get(kind, {}):
        entries.sort(key=SORTS[kind][sort])
    if request.args.get("order") == "desc":
        entries.reverse()

    per_page = min(max(request.args.get("per_page", DEFAULT_PER_PAGE, type=int), 1), MAX_PER_PAGE)
    pages = max(1, math.ceil(len(entries) / per_page))
    page = min(max(request.args.get("page", 1, type=int), 1), pages)
    start = (page - 1) * per_page

    body = {
        "results": [summarise(e) for e in entries[start:start + per_page]],
        "count": len(entries), "page": page, "per_page": per_page, "pages": pages,
    }
    if facets and _arg_bool("facets"):
        body["facets"] = facets()
    return jsonify(body)


@bp.get("/<kind>/<index>")
def get_entry(kind: str, index: str):
    if kind not in KINDS:
        abort(404, description=f"Unknown rules category '{kind}'.")
    entry = get(kind, index)
    if entry is None:
        abort(404, description=f"No {kind} entry called '{index}'.")
    return jsonify(entry)
