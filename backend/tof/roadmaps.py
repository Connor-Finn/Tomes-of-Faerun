"""Level roadmaps: a character's level-ups planned ahead of time, up to level 20.

    GET    /api/characters/<cid>/roadmaps          the character's roadmaps
    POST   /api/characters/<cid>/roadmaps          {name}   start one at the character's current level
    GET    /api/roadmaps/<rid>                     the roadmap, level by level
    PATCH  /api/roadmaps/<rid>                     {name}
    DELETE /api/roadmaps/<rid>
    GET    /api/roadmaps/<rid>/levels/<n>          the build at level n, for the builder (n may be the next
                                                   level to plan, which starts from level n-1's choices)
    PUT    /api/roadmaps/<rid>/levels/<n>          {build}  plan level n. Re-planning an earlier level
                                                   clears the levels after it.
    DELETE /api/roadmaps/<rid>/levels/<n>          remove level n and every level after it

How a roadmap is stored: every planned level keeps a complete snapshot of the character's
levelling choices at that level (its subclass and its picks). Everything else (name, race,
background, ability scores, starting equipment, items, notes) always comes from the character, so
a roadmap never changes who the character is, only how they level. Following a roadmap at level 7
is then just "take level 7's snapshot", and switching an instance onto a roadmap rewrites its
levelling choices from level 1 while keeping its items.
"""
from __future__ import annotations

import copy

from flask import Blueprint, abort, g, jsonify
from sqlalchemy import select

from .characters import engine
from .extensions import db
from .models import Character, Roadmap, utcnow
from .security import json_body, login_required, text

bp = Blueprint("roadmaps", __name__, url_prefix="/api")

MAX_ROADMAPS = 10
NAME_MAX = 60
# Picks that belong to who the character is (race, background, starting kit), not to levelling: these
# always come from the character (or the campaign instance), so following a roadmap never changes
# who someone is or takes their items away.
KEPT_PREFIXES = ("equipment:", "race:", "trait:", "background:")


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------
def snapshot(build: dict) -> dict:
    """The levelling choices in a build: what a roadmap stores for one level."""
    return {
        "subclass": build.get("subclass"),
        "choices": {k: list(v) for k, v in (build.get("choices") or {}).items() if not k.startswith(KEPT_PREFIXES)},
    }


def build_at(base: dict, snap: dict, level: int) -> dict:
    """A full build: the character's own fields with a roadmap level's choices on top."""
    out = copy.deepcopy(base)
    out["level"] = level
    out["subclass"] = snap.get("subclass")
    kept = {k: v for k, v in (base.get("choices") or {}).items() if k.startswith(KEPT_PREFIXES)}
    out["choices"] = {**copy.deepcopy(snap.get("choices") or {}), **copy.deepcopy(kept)}
    return out


def level_snapshot(levels: dict, level: int) -> dict | None:
    return levels.get(str(level))


def end_level(levels: dict) -> int:
    return max(int(k) for k in levels)


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------
def _slot_labels(result: dict) -> dict[str, str]:
    return {s["id"]: s["label"] for s in result["slots"]}


def _changes(prev: dict | None, snap: dict, result: dict) -> list[dict]:
    """What a level adds over the level before it: new picks, swapped-out picks, a subclass."""
    out = []
    if prev is not None and snap.get("subclass") and snap.get("subclass") != prev.get("subclass"):
        out.append({"label": "Subclass", "added": [engine.name_of("subclasses", snap["subclass"])], "removed": []})
    labels = _slot_labels(result)
    before = (prev or {}).get("choices") or {}
    for slot_id, values in (snap.get("choices") or {}).items():
        old = before.get(slot_id, [])
        added = [v for v in values if v not in old]
        removed = [v for v in old if v not in values]
        if prev is None or not (added or removed):
            continue
        out.append({
            "slot": slot_id,
            "label": labels.get(slot_id, slot_id),
            "added": [_value_name(v) for v in added],
            "removed": [_value_name(v) for v in removed],
        })
    return out


def _value_name(value: str) -> str:
    if value in engine.ABILITY_NAMES:
        return engine.ABILITY_NAMES[value]
    if value.startswith("feat:"):
        return engine.name_of("feats", value[5:]) or value[5:]
    return engine.pick_name(value)


def roadmap_levels(base: dict, roadmap_levels_: dict, start: int) -> list[dict]:
    """Every planned level with what it brings, and whether it still fits the character."""
    out = []
    prev = None
    prev_features: set[str] = set()
    for n in range(start, end_level(roadmap_levels_) + 1):
        snap = roadmap_levels_[str(n)]
        build = build_at(base, snap, n)
        result = engine.check(build, previous_level=n)
        features = [f for f in result["sheet"]["features"] if f["source"] in ("class", "subclass", "feat")]
        names = {f["index"] for f in features}
        out.append({
            "level": n,
            "start": n == start,
            "hit_points": result["sheet"]["hit_points"],
            "subclass": engine.name_of("subclasses", snap.get("subclass")),
            "new_features": [] if prev is None else [f["name"] for f in features if f["index"] not in prev_features],
            "changes": _changes(prev, snap, result),
            "fits": result["complete"],
            "problems": [p["message"] for p in result["errors"] + result["missing"]],
        })
        prev, prev_features = snap, names
    return out


def summary(r: Roadmap) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "character_id": r.character_id,
        "start_level": r.start_level,
        "end_level": r.end_level,
        "followed_by": sorted(
            ({"campaign": {"id": f.instance.campaign.id, "name": f.instance.campaign.name}, "level": f.instance.build.get("level", 1)}
             for f in r.followers),
            key=lambda x: x["campaign"]["name"].lower()),
        "updated_at": r.updated_at.isoformat() + "Z",
    }


def detail(r: Roadmap) -> dict:
    c = r.character
    return {"roadmap": {**summary(r), "levels": roadmap_levels(c.build, r.levels, r.start_level)},
            "character": c.to_dict()}


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
def _my_character(character_id: int) -> Character:
    character = db.session.get(Character, character_id)
    if character is None or character.user_id != g.user.id:
        abort(404, description="Character not found.")
    return character


def _my_roadmap(roadmap_id: int) -> Roadmap:
    roadmap = db.session.get(Roadmap, roadmap_id)
    if roadmap is None or roadmap.character.user_id != g.user.id:
        abort(404, description="Roadmap not found.")
    return roadmap


def _name(data: dict, current: str | None = None) -> str:
    name = text(data, "name") if "name" in data else (current or "")
    if not name:
        abort(400, description="Give the roadmap a name.")
    if len(name) > NAME_MAX:
        abort(400, description=f"Keep the name to {NAME_MAX} characters or fewer.")
    return name


# ---------------------------------------------------------------------------
# Roadmaps
# ---------------------------------------------------------------------------
@bp.get("/characters/<int:character_id>/roadmaps")
@login_required
def list_roadmaps(character_id: int):
    character = _my_character(character_id)
    return jsonify(roadmaps=[summary(r) for r in character.roadmaps], limit=MAX_ROADMAPS,
                   can_start=character.is_complete and character.build.get("level", 1) < engine.MAX_LEVEL)


@bp.post("/characters/<int:character_id>/roadmaps")
@login_required
def create_roadmap(character_id: int):
    character = _my_character(character_id)
    name = _name(json_body())
    if not character.is_complete:
        abort(400, description=f"{character.name} is still a draft. Finish the character before planning level-ups.")
    level = character.build.get("level", 1)
    if level >= engine.MAX_LEVEL:
        abort(400, description=f"{character.name} is already level {engine.MAX_LEVEL}: there's nothing left to plan.")
    if len(character.roadmaps) >= MAX_ROADMAPS:
        abort(400, description=f"A character can have up to {MAX_ROADMAPS} roadmaps. Delete one to make room.")
    roadmap = Roadmap(character=character, name=name, start_level=level,
                      levels={str(level): snapshot(character.build)})
    db.session.add(roadmap)
    db.session.commit()
    return jsonify(message=f"Roadmap “{name}” started at level {level}.", **detail(roadmap)), 201


@bp.get("/roadmaps/<int:roadmap_id>")
@login_required
def get_roadmap(roadmap_id: int):
    return jsonify(detail(_my_roadmap(roadmap_id)))


@bp.patch("/roadmaps/<int:roadmap_id>")
@login_required
def rename_roadmap(roadmap_id: int):
    roadmap = _my_roadmap(roadmap_id)
    roadmap.name = _name(json_body(), roadmap.name)
    db.session.commit()
    return jsonify(message="Roadmap renamed.", **detail(roadmap))


@bp.delete("/roadmaps/<int:roadmap_id>")
@login_required
def delete_roadmap(roadmap_id: int):
    roadmap = _my_roadmap(roadmap_id)
    following = len(roadmap.followers)
    db.session.delete(roadmap)
    db.session.commit()
    extra = (f" {following} campaign character{'s' if following != 1 else ''} stopped following it and kept "
             f"{'their' if following != 1 else 'its'} choices.") if following else ""
    return jsonify(message=f"Roadmap “{roadmap.name}” was deleted.{extra}")


# ---------------------------------------------------------------------------
# Levels
# ---------------------------------------------------------------------------
def _plannable(roadmap: Roadmap, level: int) -> None:
    if level <= roadmap.start_level:
        abort(400, description=f"Level {roadmap.start_level} is where the roadmap starts, from the character itself. "
                               f"Plan the levels after it.")
    if level > engine.MAX_LEVEL:
        abort(400, description=f"Roadmaps go up to level {engine.MAX_LEVEL}.")
    if level > roadmap.end_level + 1:
        abort(400, description=f"Plan level {roadmap.end_level + 1} first.")


@bp.get("/roadmaps/<int:roadmap_id>/levels/<int:level>")
@login_required
def get_level(roadmap_id: int, level: int):
    roadmap = _my_roadmap(roadmap_id)
    character = roadmap.character
    if level < roadmap.start_level or level > min(roadmap.end_level + 1, engine.MAX_LEVEL):
        abort(404, description="That level isn't planned yet.")
    planned = str(level) in roadmap.levels
    snap = roadmap.levels[str(level)] if planned else roadmap.levels[str(level - 1)]
    build = engine.clean(build_at(character.build, snap, level))
    result = engine.check(build, build_mode=character.build_mode, previous_level=level)
    return jsonify(roadmap=summary(roadmap), character={**character.to_dict(), "build": build},
                   level=level, planned=planned, later_levels=max(0, roadmap.end_level - level), **result)


@bp.put("/roadmaps/<int:roadmap_id>/levels/<int:level>")
@login_required
def plan_level(roadmap_id: int, level: int):
    roadmap = _my_roadmap(roadmap_id)
    _plannable(roadmap, level)
    build = json_body().get("build")
    if not isinstance(build, dict) or ("choices" in build and not isinstance(build["choices"], dict)):
        abort(400, description="Send the build as an object.")
    character = roadmap.character
    full = engine.clean(build_at(character.build, snapshot(build), level))
    result = engine.check(full, previous_level=level)
    if not result["valid"]:
        return jsonify(error="That plan breaks the rules.", errors=result["errors"]), 400
    if not result["complete"]:
        return jsonify(error=f"Make every choice for level {level} before saving it to the roadmap.",
                       errors=result["missing"]), 400
    levels = {k: v for k, v in roadmap.levels.items() if int(k) < level}
    dropped = roadmap.end_level - level if roadmap.end_level > level else 0
    levels[str(level)] = snapshot(full)
    roadmap.levels = levels
    roadmap.updated_at = utcnow()
    db.session.commit()
    extra = f" The {dropped} level{'s' if dropped != 1 else ''} planned after it {'were' if dropped != 1 else 'was'} cleared." if dropped else ""
    return jsonify(message=f"Level {level} is planned in “{roadmap.name}”.{extra}", **detail(roadmap))


@bp.delete("/roadmaps/<int:roadmap_id>/levels/<int:level>")
@login_required
def remove_levels(roadmap_id: int, level: int):
    roadmap = _my_roadmap(roadmap_id)
    if level <= roadmap.start_level or str(level) not in roadmap.levels:
        abort(400, description="Choose a planned level after the roadmap's first one.")
    roadmap.levels = {k: v for k, v in roadmap.levels.items() if int(k) < level}
    roadmap.updated_at = utcnow()
    db.session.commit()
    return jsonify(message=f"Removed level {level} and up from “{roadmap.name}”.", **detail(roadmap))


# ---------------------------------------------------------------------------
# Used by campaigns (following) and publishing (copying)
# ---------------------------------------------------------------------------
def followed_build(instance_build: dict, roadmap_levels_: dict, level: int) -> dict:
    """An instance's build rewritten to a roadmap's level: its items and starting kit stay."""
    return engine.clean(build_at(instance_build, roadmap_levels_[str(level)], level))


def copy_levels(levels: dict) -> dict:
    return copy.deepcopy(levels)


def character_roadmaps(character_id: int) -> list[Roadmap]:
    return list(db.session.scalars(select(Roadmap).where(Roadmap.character_id == character_id).order_by(Roadmap.id)))
