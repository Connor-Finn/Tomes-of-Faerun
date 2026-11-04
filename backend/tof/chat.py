"""Party chat: the enchanted parchment every party writes on.

    GET    /api/parties/<id>/messages              the latest messages, who's writing, and your unread mark
           ?before=<message id>                    older messages, for turning back the page
    POST   /api/parties/<id>/messages              {body}   write a message
    DELETE /api/parties/<id>/messages/<msg id>     strike a message out (its author, or the party's DM)
    POST   /api/parties/<id>/writing               "I'm writing": others see it for a few seconds

Only the party's DM and its members (not players who are merely invited) can read or write.

The browser polls the first endpoint every couple of seconds. It always gets the whole latest page,
so new messages and struck-out ones both show up without any extra bookkeeping. Reading the latest
page marks the chat as read, which is what the unread counts on the party lists use.
"""
from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import func, select

from .extensions import db
from .models import Party, PartyChatState, PartyMessage, User, utcnow
from .parties import is_member, person
from .security import json_body, login_required, text

bp = Blueprint("chat", __name__, url_prefix="/api/parties")

PAGE_SIZE = 50
BODY_MAX = 1000
WRITING_SECONDS = 6


def _party(party_id: int) -> Party:
    party = db.session.get(Party, party_id)
    if party is None or not (party.dm_id == g.user.id or is_member(party, g.user)):
        abort(404, description="Party not found.")
    return party


def _state(party: Party, user: User) -> PartyChatState:
    state = db.session.scalar(select(PartyChatState).filter_by(party_id=party.id, user_id=user.id))
    if state is None:
        state = PartyChatState(party_id=party.id, user_id=user.id, last_read_id=0)
        db.session.add(state)
    return state


def _message(m: PartyMessage, party: Party) -> dict:
    mine = m.author_id == g.user.id
    return {
        "id": m.id,
        "body": m.body,
        "author": person(m.author) if m.author else None,
        "from_dm": m.author_id == party.dm_id,
        "mine": mine,
        "can_strike": mine or party.dm_id == g.user.id,
        "created_at": m.created_at.isoformat() + "Z",
    }


def unread_count(party: Party, user: User) -> int:
    """Messages other people wrote since `user` last read the chat."""
    state = db.session.scalar(select(PartyChatState).filter_by(party_id=party.id, user_id=user.id))
    last = state.last_read_id if state else 0
    return db.session.scalar(
        select(func.count()).select_from(PartyMessage).where(
            PartyMessage.party_id == party.id, PartyMessage.id > last,
            (PartyMessage.author_id != user.id) | PartyMessage.author_id.is_(None))) or 0


def _writing(party: Party) -> list[str]:
    since = utcnow() - timedelta(seconds=WRITING_SECONDS)
    states = db.session.scalars(select(PartyChatState).where(
        PartyChatState.party_id == party.id, PartyChatState.user_id != g.user.id,
        PartyChatState.writing_at.is_not(None), PartyChatState.writing_at >= since))
    people = {s.user_id for s in states}
    # Only people who are still in the party (someone could leave mid-sentence).
    allowed = {party.dm_id} | {m.user_id for m in party.members if m.status == "member"}
    return sorted(u.name for u in (db.session.get(User, uid) for uid in people & allowed) if u)


@bp.get("/<int:party_id>/messages")
@login_required
def messages(party_id: int):
    party = _party(party_id)
    stmt = select(PartyMessage).where(PartyMessage.party_id == party.id)
    before = request.args.get("before", type=int)
    if before:
        stmt = stmt.where(PartyMessage.id < before)
    page = list(db.session.scalars(stmt.order_by(PartyMessage.id.desc()).limit(PAGE_SIZE + 1)))
    has_more = len(page) > PAGE_SIZE
    page = list(reversed(page[:PAGE_SIZE]))

    state = _state(party, g.user)
    last_read = state.last_read_id
    if not before and page and page[-1].id > state.last_read_id:
        state.last_read_id = page[-1].id
    db.session.commit()
    return jsonify(
        messages=[_message(m, party) for m in page],
        has_more=has_more,
        last_read_id=last_read,
        writing=_writing(party) if not before else [],
    )


@bp.post("/<int:party_id>/messages")
@login_required
def write(party_id: int):
    party = _party(party_id)
    body = text(json_body(), "body")
    if not body:
        return jsonify(error="Write something first.", errors={"body": "Write something first."}), 400
    if len(body) > BODY_MAX:
        error = f"Keep a message to {BODY_MAX} characters or fewer."
        return jsonify(error=error, errors={"body": error}), 400
    message = PartyMessage(party_id=party.id, author_id=g.user.id, body=body)
    db.session.add(message)
    db.session.flush()
    state = _state(party, g.user)
    state.writing_at = None
    state.last_read_id = message.id
    db.session.commit()
    return jsonify(message=_message(message, party)), 201


@bp.delete("/<int:party_id>/messages/<int:message_id>")
@login_required
def strike(party_id: int, message_id: int):
    party = _party(party_id)
    message = db.session.get(PartyMessage, message_id)
    if message is None or message.party_id != party.id:
        abort(404, description="That message has already faded.")
    if message.author_id != g.user.id and party.dm_id != g.user.id:
        abort(403, description="Only the writer or the party's Dungeon Master can strike a message out.")
    db.session.delete(message)
    db.session.commit()
    return jsonify(message="The message faded from the page.")


@bp.post("/<int:party_id>/writing")
@login_required
def writing(party_id: int):
    party = _party(party_id)
    _state(party, g.user).writing_at = utcnow()
    db.session.commit()
    return jsonify(ok=True)
