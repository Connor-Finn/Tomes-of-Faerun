"""The items catalogue: SRD equipment and magic items in one tome, plus each user's favourites.

    GET    /api/items                        equipment and magic items together (search, filters,
                                             sort, pages), each with `favourite`; ?favourites=1 for
                                             only your favourites
    GET    /api/items/<index>                one item in full: its kind, whether it's a favourite and
                                             which of your characters carry it
    GET    /api/items/favourites             your favourite items
    PUT    /api/items/favourites/<index>     star an item
    DELETE /api/items/favourites/<index>     unstar it

Filters: q (name), kind (equipment | magic), category (an equipment category index such as
"weapon" or "wondrous-items"), rarity (magic items only), favourites=1, sort (name | category |
cost | rarity) and order=desc.

Equipment and magic items are two separate SRD lists whose indexes never clash, so an item is
identified by its index alone. Magic items with variants ("Armor, +1, +2, or +3") are listed once;
their variants are on the item's page.
"""
from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable
from functools import lru_cache

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import select

from . import rules
from .extensions import db
from .models import Character, FavouriteItem
from .rules.api import DEFAULT_PER_PAGE, MAX_PER_PAGE, _arg_bool, _arg_list, _options
from .security import login_required

bp = Blueprint("items", __name__, url_prefix="/api/items")

KINDS = {"equipment": "equipment", "magic": "magic-items"}
RARITIES = ["Common", "Uncommon", "Rare", "Very Rare", "Legendary", "Artifact", "Varies"]
# Copper pieces per coin, for sorting by cost
COIN = {"cp": 1, "sp": 10, "ep": 50, "gp": 100, "pp": 1000}


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
def find(index: str) -> tuple[str, dict] | None:
    """('equipment' | 'magic', entry) for an item index, or None."""
    for kind, rules_kind in KINDS.items():
        if entry := rules.get(rules_kind, index):
            return kind, entry
    return None


def _item(index: str) -> tuple[str, dict]:
    found = find(index)
    if found is None:
        abort(404, description=f"There's no item called '{index}' in the tome.")
    return found


def attunement(item: dict) -> str | None:
    """'requires attunement by a spellcaster' from a magic item's first line, or None."""
    first = (item.get("desc") or [""])[0]
    if "(requires attunement" not in first:
        return None
    return first[first.index("(requires attunement") + 1:].rstrip(")")


def item_type(item: dict) -> str:
    """The line under an item's name: 'Wondrous item, uncommon' or 'Martial melee weapon'."""
    if "rarity" in item:
        # "Armor (medium or heavy, but not hide), uncommon (requires attunement)" -> "Armor (medium or heavy, but not hide)"
        first = (item.get("desc") or [""])[0].split(" (requires attunement")[0]
        cut = re.search(r", (?:common|uncommon|rare|very rare|legendary|artifact)\b", first, re.IGNORECASE)
        kind_of = first[:cut.start()] if cut else item["equipment_category"]["name"]
        # The SRD spells it "Wondous item" once, and its category is "Wondrous Items"
        return "Wondrous item" if kind_of.lower().startswith(("wondous", "wondrous")) else kind_of
    if item.get("category_range"):
        return f"{item['category_range']} weapon"
    if item.get("armor_category"):
        return "Shield" if item["armor_category"] == "Shield" else f"{item['armor_category']} armor"
    sub = (item.get("gear_category") or {}).get("name") or item.get("tool_category") or item.get("vehicle_category")
    return sub or item["equipment_category"]["name"]


def summary(kind: str, item: dict) -> dict:
    cost = item.get("cost") or {}
    return {
        "index": item["index"], "name": item["name"], "kind": kind,
        "category": item["equipment_category"]["name"], "category_index": item["equipment_category"]["index"],
        "type": item_type(item),
        "cost": f"{cost['quantity']} {cost['unit']}" if cost else None,
        "weight": item.get("weight"),
        "rarity": item["rarity"]["name"] if kind == "magic" else None,
        "attunement": attunement(item) if kind == "magic" else None,
    }


@lru_cache(maxsize=None)
def catalogue() -> tuple[tuple[str, dict], ...]:
    """Every item, equipment and magic, by name. Magic item variants are left out."""
    items = [("equipment", e) for e in rules.load("equipment")]
    items += [("magic", m) for m in rules.load("magic-items") if not m.get("variant")]
    return tuple(sorted(items, key=lambda ki: ki[1]["name"].lower()))


def _cost_cp(item: dict) -> float:
    cost = item.get("cost")
    return cost["quantity"] * COIN.get(cost["unit"], 100) if cost else math.inf


SORTS: dict[str, Callable[[tuple[str, dict]], object]] = {
    "name": lambda ki: ki[1]["name"].lower(),
    "category": lambda ki: (ki[1]["equipment_category"]["name"], ki[1]["name"].lower()),
    "cost": lambda ki: (_cost_cp(ki[1]), ki[1]["name"].lower()),
    "rarity": lambda ki: (RARITIES.index(ki[1]["rarity"]["name"]) if ki[0] == "magic" else -1, ki[1]["name"].lower()),
}


def facets() -> dict:
    return {
        "kind": [{"value": "equipment", "label": "Equipment"}, {"value": "magic", "label": "Magic items"}],
        "category": _options((i["equipment_category"]["index"], i["equipment_category"]["name"]) for _, i in catalogue()),
        "rarity": [{"value": r.lower(), "label": r} for r in RARITIES
                   if any(k == "magic" and i["rarity"]["name"] == r for k, i in catalogue())],
    }


def _filters() -> list[Callable[[tuple[str, dict]], bool]]:
    filters = []
    kinds = _arg_list("kind")
    if unknown := [k for k in kinds if k not in KINDS]:
        abort(400, description=f"Unknown kind '{unknown[0]}'. Use 'equipment' or 'magic'.")
    if kinds:
        filters.append(lambda ki: ki[0] in kinds)
    if cats := _arg_list("category"):
        filters.append(lambda ki: ki[1]["equipment_category"]["index"] in cats)
    if rarities := _arg_list("rarity"):
        filters.append(lambda ki: ki[0] == "magic" and ki[1]["rarity"]["name"].lower() in rarities)
    if _arg_bool("attunement") is not None:
        wanted = _arg_bool("attunement")
        filters.append(lambda ki: ki[0] == "magic" and (attunement(ki[1]) is not None) == wanted)
    return filters


# ---------------------------------------------------------------------------
# Favourites and characters
# ---------------------------------------------------------------------------
def _favourites() -> set[str]:
    return set(db.session.scalars(select(FavouriteItem.item).where(FavouriteItem.user_id == g.user.id)))


def _characters_with(index: str) -> list[dict]:
    """Your characters who carry the item, and how many."""
    from .characters import engine

    out = []
    stmt = select(Character).where(Character.user_id == g.user.id).order_by(Character.name)
    for c in db.session.scalars(stmt):
        a = engine.analyse(dict(c.build))
        qty = a.inventory.get(index, 0) + a.magic_items.get(index, 0)
        if qty:
            out.append({"id": c.id, "name": c.name or "Unnamed adventurer", "quantity": qty,
                        "added": index in (c.build.get("items") or {})})
    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@bp.get("")
@login_required
def items():
    favourites = _favourites()
    entries: Iterable[tuple[str, dict]] = catalogue()
    if q := request.args.get("q", "").strip().lower():
        entries = [ki for ki in entries if q in ki[1]["name"].lower()]
    filters = _filters()
    if _arg_bool("favourites"):
        filters.append(lambda ki: ki[1]["index"] in favourites)
    for keep in filters:
        entries = [ki for ki in entries if keep(ki)]
    entries = list(entries)

    sort = request.args.get("sort", "name")
    if sort not in SORTS:
        abort(400, description=f"Can't sort by '{sort}'. Use name, category, cost or rarity.")
    entries.sort(key=SORTS[sort])
    if request.args.get("order") == "desc":
        entries.reverse()

    per_page = min(max(request.args.get("per_page", DEFAULT_PER_PAGE, type=int), 1), MAX_PER_PAGE)
    pages = max(1, math.ceil(len(entries) / per_page))
    page = min(max(request.args.get("page", 1, type=int), 1), pages)
    start = (page - 1) * per_page
    results = [{**summary(k, i), "favourite": i["index"] in favourites} for k, i in entries[start:start + per_page]]

    body = {"results": results, "count": len(entries), "page": page, "per_page": per_page, "pages": pages,
            "favourite_count": len(favourites)}
    if _arg_bool("facets"):
        body["facets"] = facets()
    return jsonify(body)


@bp.get("/favourites")
@login_required
def favourites():
    found = [f for i in _favourites() if (f := find(i))]
    return jsonify(favourites=sorted((summary(k, i) for k, i in found), key=lambda s: s["name"].lower()))


@bp.get("/<index>")
@login_required
def item(index: str):
    kind, entry = _item(index)
    return jsonify(item=entry, kind=kind, summary=summary(kind, entry), favourite=index in _favourites(),
                   characters=_characters_with(index))


@bp.put("/favourites/<index>")
@login_required
def add_favourite(index: str):
    _, entry = _item(index)
    if index not in _favourites():
        db.session.add(FavouriteItem(user_id=g.user.id, item=index))
        db.session.commit()
    return jsonify(message=f"{entry['name']} is one of your favourites.", favourite=True)


@bp.delete("/favourites/<index>")
@login_required
def remove_favourite(index: str):
    _, entry = _item(index)
    fav = db.session.scalar(select(FavouriteItem).where(FavouriteItem.user_id == g.user.id,
                                                        FavouriteItem.item == index))
    if fav is not None:
        db.session.delete(fav)
        db.session.commit()
    return jsonify(message=f"{entry['name']} was taken off your favourites.", favourite=False)
