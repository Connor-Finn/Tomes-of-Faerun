"""Character Manager API: /api/characters.

    GET    /api/characters/options      races, classes, backgrounds... for the builder's first choices
    GET    /api/characters/templates    premade characters to start from
    POST   /api/characters/check        analyse a build without saving it (the builder calls this live)
    GET    /api/characters              your characters
    POST   /api/characters              create one, from a build or from a template
    GET    /api/characters/<id>         the character, its sheet and its open choices
    PATCH  /api/characters/<id>         change the build, the name or the build mode
    DELETE /api/characters/<id>

Rules are enforced here, not in the browser: a build with an illegal pick is refused with 400 and
the reasons. A build that is legal but unfinished is saved as a draft.
"""
from __future__ import annotations

import copy

from flask import Blueprint, abort, g, jsonify
from sqlalchemy import func, select

from .. import rules
from ..extensions import db
from ..models import Character
from ..security import json_body, login_required
from . import engine, templates

bp = Blueprint("characters", __name__, url_prefix="/api/characters")

MAX_CHARACTERS = 50


@bp.get("/options")
def options():
    """The first choices in the builder. Everything after these comes from /check as slots."""
    return jsonify(
        races=[{
            "index": r["index"], "name": r["name"], "speed": r["speed"], "size": r["size"],
            "ability_bonuses": [{"ability": b["ability_score"]["index"], "bonus": b["bonus"]} for b in r["ability_bonuses"]],
            "subraces": [{"index": s["index"], "name": s["name"], "desc": rules.get("subraces", s["index"])["desc"]}
                         for s in r["subraces"]],
            "traits": [t["name"] for t in r["traits"]],
            "summary": r.get("alignment", ""),
            "age": r.get("age", ""),
        } for r in rules.load("races")],
        classes=[{
            "index": c["index"], "name": c["name"], "hit_die": c["hit_die"],
            "saving_throws": [s["index"] for s in c["saving_throws"]],
            "spellcaster": bool(c.get("spellcasting")),
            "spellcasting_ability": (c.get("spellcasting") or {}).get("spellcasting_ability", {}).get("index"),
            "subclass_level": engine.subclass_level(c["index"]),
            "subclasses": [{"index": s["index"], "name": s["name"],
                            "desc": " ".join(rules.get("subclasses", s["index"])["desc"])} for s in c["subclasses"]],
        } for c in rules.load("classes")],
        backgrounds=[{
            "index": b["index"], "name": b["name"],
            "skills": [engine.strip_prefix(p["name"]) for p in b["starting_proficiencies"]],
            "feature": b.get("feature", {}).get("name"),
        } for b in rules.load("backgrounds")],
        alignments=[{"index": a["index"], "name": a["name"], "desc": a.get("desc", "")} for a in rules.load("alignments")],
        abilities=[{"key": k, "name": v} for k, v in engine.ABILITY_NAMES.items()],
        ability_methods=[{"value": k, "label": v} for k, v in engine.ABILITY_METHODS.items()],
        standard_array=engine.STANDARD_ARRAY,
        point_buy={"budget": engine.POINT_BUY_BUDGET, "costs": engine.POINT_BUY_COST},
        build_modes=list(engine.BUILD_MODES),
        easy_max_level=engine.EASY_MAX_CREATION_LEVEL,
        max_level=engine.MAX_LEVEL,
        note_fields=list(engine.NOTE_FIELDS),
    )


@bp.get("/templates")
def list_templates():
    return jsonify(templates=[templates.summary(t) for t in templates.premades().values()])


def _build_mode(data: dict, default: str) -> str:
    mode = data.get("build_mode", default)
    if mode not in engine.BUILD_MODES:
        abort(400, description="Build mode must be “easy” or “standard”.")
    return mode


def _build(data: dict) -> dict:
    build = data.get("build")
    if not isinstance(build, dict):
        abort(400, description="Send the character's build as an object.")
    if "choices" in build and not isinstance(build["choices"], dict):
        abort(400, description="Choices must be an object.")
    return build


@bp.post("/check")
@login_required
def check():
    data = json_body()
    return jsonify(engine.check(_build(data), build_mode=_build_mode(data, "standard")))


def _owned(character_id: int) -> Character:
    character = db.session.get(Character, character_id)
    if character is None or character.user_id != g.user.id:
        abort(404, description="Character not found.")
    return character


def _save(character: Character, build: dict, build_mode: str, previous_level: int):
    """Validate and store a build. Returns an error response, or None when saved."""
    cleaned = engine.clean(build)
    result = engine.check(cleaned, build_mode=build_mode, previous_level=previous_level)
    if not result["valid"]:
        return {"error": "That build breaks the rules.", "errors": result["errors"]}, 400
    character.build = cleaned
    character.name = cleaned["name"]
    character.build_mode = build_mode
    character.is_complete = result["complete"]
    return None


def _detail(character: Character) -> dict:
    result = engine.check(character.build, build_mode=character.build_mode, previous_level=character.build.get("level", 1))
    return {"character": {**character.to_dict(), "build": character.build}, **result}


@bp.get("")
@login_required
def list_characters():
    stmt = select(Character).where(Character.user_id == g.user.id).order_by(Character.updated_at.desc(), Character.id.desc())
    return jsonify(characters=[c.to_dict() for c in db.session.scalars(stmt)], limit=MAX_CHARACTERS)


@bp.post("")
@login_required
def create():
    data = json_body()
    count = db.session.scalar(select(func.count()).select_from(Character).where(Character.user_id == g.user.id))
    if count >= MAX_CHARACTERS:
        abort(400, description=f"You can keep up to {MAX_CHARACTERS} characters. Delete one to make room.")

    template_id = data.get("template")
    if template_id:
        template = templates.get(str(template_id))
        if template is None:
            abort(404, description="Template not found.")
        build = copy.deepcopy(template["build"])
        mode = _build_mode(data, template.get("build_mode", "standard"))
        previous_level = build.get("level", 1)   # a template's level is never refused
    else:
        build = _build(data)
        mode = _build_mode(data, "standard")
        previous_level = 0

    character = Character(user_id=g.user.id, template=template_id or None)
    if error := _save(character, build, mode, previous_level):
        return error
    db.session.add(character)
    db.session.commit()
    return jsonify(_detail(character)), 201


@bp.get("/<int:character_id>")
@login_required
def detail(character_id: int):
    return jsonify(_detail(_owned(character_id)))


@bp.patch("/<int:character_id>")
@login_required
def update(character_id: int):
    character = _owned(character_id)
    data = json_body()
    build = copy.deepcopy(character.build)
    if "build" in data:
        build = _build(data)
    if "name" in data:
        build["name"] = data["name"]
    if "notes" in data:
        build["notes"] = data["notes"]
    mode = _build_mode(data, character.build_mode)
    if error := _save(character, build, mode, previous_level=character.build.get("level", 1)):
        return error
    db.session.commit()
    return jsonify(_detail(character))


@bp.delete("/<int:character_id>")
@login_required
def delete(character_id: int):
    character = _owned(character_id)
    db.session.delete(character)
    db.session.commit()
    return jsonify(message=f"{character.name or 'The character'} was deleted.")
