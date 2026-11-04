"""Published characters: templates players share with everyone.

    GET    /api/published                 every published character  ?q=<name or author>&class=<index>
    GET    /api/published/mine            the characters you've published
    POST   /api/published                 {character_id, summary}   publish one of your finished characters
    DELETE /api/published/<id>            unpublish (copies other players already made are theirs to keep)

Copying one into your own characters is POST /api/characters {published: <id>}, which works exactly
like starting from a premade template.

Publishing takes a snapshot of the build (choices, equipment, spells and notes). Later edits to the
author's character never change it. Level roadmaps will be attachable once roadmaps exist.
"""
from __future__ import annotations

import copy

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import select

from .characters import engine
from .extensions import db
from .models import Character, PublishedCharacter
from .parties import person
from .security import json_body, login_required, text

bp = Blueprint("published", __name__, url_prefix="/api/published")

MAX_PUBLISHED = 20
SUMMARY_MAX = 300


def summary(p: PublishedCharacter) -> dict:
    sheet = engine.sheet(engine.analyse(p.build))
    s = sheet["summary"]
    return {
        "id": p.id,
        "name": p.name,
        "summary": p.summary,
        "author": person(p.author),
        "mine": p.author_id == g.user.id,
        "level": s["level"],
        "race": s["subrace"] or s["race"],
        "class": s["class"],
        "class_index": p.build.get("class"),
        "subclass": s.get("subclass"),
        "background": s["background"],
        "build_mode": p.build_mode,
        "hit_points": sheet["hit_points"],
        "armor_class": sheet["armor_class"],
        "copies": p.copies,
        "character_id": p.character_id if p.author_id == g.user.id else None,
        "published_at": p.created_at.isoformat() + "Z",
    }


def get_published(published_id) -> PublishedCharacter:
    try:
        published = db.session.get(PublishedCharacter, int(published_id))
    except (TypeError, ValueError):
        published = None
    if published is None:
        abort(404, description="That published character has been taken down.")
    return published


@bp.get("")
@login_required
def browse():
    q = request.args.get("q", "").strip().lower()
    cls = request.args.get("class", "").strip()
    rows = db.session.scalars(select(PublishedCharacter).order_by(PublishedCharacter.created_at.desc(),
                                                                  PublishedCharacter.id.desc()))
    out = []
    for p in rows:
        if cls and p.build.get("class") != cls:
            continue
        if q and q not in p.name.lower() and q not in p.author.name.lower():
            continue
        out.append(summary(p))
    return jsonify(published=out)


@bp.get("/mine")
@login_required
def mine():
    rows = sorted(g.user.published, key=lambda p: (p.created_at, p.id), reverse=True)
    return jsonify(published=[summary(p) for p in rows], limit=MAX_PUBLISHED)


@bp.post("")
@login_required
def publish():
    data = json_body()
    cid = data.get("character_id")
    character = db.session.get(Character, cid) if isinstance(cid, int) and not isinstance(cid, bool) else None
    if character is None or character.user_id != g.user.id:
        return jsonify(error="Choose one of your characters to publish.",
                       errors={"character_id": "Choose one of your characters to publish."}), 400
    if not character.is_complete:
        error = f"{character.name or 'That character'} is still a draft. Finish it before publishing."
        return jsonify(error=error, errors={"character_id": error}), 400
    blurb = text(data, "summary")
    if len(blurb) > SUMMARY_MAX:
        error = f"Keep the description to {SUMMARY_MAX} characters or fewer."
        return jsonify(error=error, errors={"summary": error}), 400
    if len(g.user.published) >= MAX_PUBLISHED:
        abort(400, description=f"You can have up to {MAX_PUBLISHED} published characters. Unpublish one to make room.")
    if any(p.character_id == character.id and p.build == character.build for p in g.user.published):
        error = f"{character.name} is already published exactly as it is now."
        return jsonify(error=error, errors={"character_id": error}), 400

    published = PublishedCharacter(
        author_id=g.user.id, character_id=character.id, name=character.name, summary=blurb,
        build=copy.deepcopy(character.build), build_mode=character.build_mode)
    db.session.add(published)
    db.session.commit()
    return jsonify(message=f"{published.name} is published. Other players can now start from it.",
                   published=summary(published)), 201


@bp.delete("/<int:published_id>")
@login_required
def unpublish(published_id: int):
    published = db.session.get(PublishedCharacter, published_id)
    if published is None or published.author_id != g.user.id:
        abort(404, description="That published character isn't yours.")
    db.session.delete(published)
    db.session.commit()
    return jsonify(message=f"{published.name} was unpublished. Copies other players made are still theirs.")
