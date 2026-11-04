"""The spell catalogue: every SRD spell, plus each user's favourites.

    GET    /api/spells                        the SRD spells (search, filters, sort, pages), each with
                                              `favourite`; add ?favourites=1 for only your favourites
    GET    /api/spells/<index>                one spell's full rules text, whether it's a favourite,
                                              and which of your characters have it
    GET    /api/spells/favourites             your favourite spells
    PUT    /api/spells/favourites/<index>     star a spell
    DELETE /api/spells/favourites/<index>     unstar it

The filters are the rules API's (q, level, school, class, ritual, concentration, sort). Favourites
are stored by the spell's rules `index`, so the text always comes from the SRD data. Which spells a
character may learn is the character engine's job (characters/engine.py): favourites never change
what's legal, they only help you find spells.
"""
from __future__ import annotations

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import select

from . import rules
from .extensions import db
from .models import Character, FavouriteSpell
from .rules.api import catalogue_page, spell_summary
from .security import login_required

bp = Blueprint("spells", __name__, url_prefix="/api/spells")

# Where a spell sits in a character's build, by the start of the choice's slot id.
SOURCES = {
    "spells:cantrips": "Cantrip",
    "spells:known": "Known",
    "spells:spellbook": "Spellbook",
    "spells:prepared": "Prepared",
    "spells:magical-secrets": "Magical Secrets",
    "spells:arcanum": "Mystic Arcanum",
    "trait:": "Racial trait",
}


def _spell(index: str) -> dict:
    spell = rules.get("spells", index)
    if spell is None:
        abort(404, description=f"There's no spell called '{index}' in the tome.")
    return spell


def _favourites() -> set[str]:
    return set(db.session.scalars(select(FavouriteSpell.spell).where(FavouriteSpell.user_id == g.user.id)))


def _characters_with(index: str) -> list[dict]:
    """Your characters whose build includes the spell, and how they got it."""
    out = []
    stmt = select(Character).where(Character.user_id == g.user.id).order_by(Character.name)
    for c in db.session.scalars(stmt):
        sources = []
        for slot_id, picks in (c.build.get("choices") or {}).items():
            if isinstance(picks, list) and index in picks:
                label = next((v for k, v in SOURCES.items() if slot_id.startswith(k)), None)
                if label and label not in sources:
                    sources.append(label)
        if sources:
            out.append({"id": c.id, "name": c.name or "Unnamed adventurer", "sources": sources})
    return out


@bp.get("")
@login_required
def spells():
    favourites = _favourites()
    extra = [lambda s: s["index"] in favourites] if request.args.get("favourites") in ("1", "true") else []
    body = catalogue_page("spells", extra)
    for s in body["results"]:
        s["favourite"] = s["index"] in favourites
    body["favourite_count"] = len(favourites)
    return jsonify(body)


@bp.get("/favourites")
@login_required
def favourites():
    spells = [rules.get("spells", i) for i in _favourites()]
    summaries = sorted((spell_summary(s) for s in spells if s), key=lambda s: (s["level"], s["name"]))
    return jsonify(favourites=summaries)


@bp.get("/<index>")
@login_required
def spell(index: str):
    entry = _spell(index)
    return jsonify(spell=entry, favourite=index in _favourites(), characters=_characters_with(index))


@bp.put("/favourites/<index>")
@login_required
def add_favourite(index: str):
    spell = _spell(index)
    if index not in _favourites():
        db.session.add(FavouriteSpell(user_id=g.user.id, spell=index))
        db.session.commit()
    return jsonify(message=f"{spell['name']} is one of your favourites.", favourite=True)


@bp.delete("/favourites/<index>")
@login_required
def remove_favourite(index: str):
    spell = _spell(index)
    fav = db.session.scalar(select(FavouriteSpell).where(FavouriteSpell.user_id == g.user.id,
                                                         FavouriteSpell.spell == index))
    if fav is not None:
        db.session.delete(fav)
        db.session.commit()
    return jsonify(message=f"{spell['name']} was taken off your favourites.", favourite=False)
