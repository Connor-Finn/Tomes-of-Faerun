"""Friends and people search: finding other adventurers and keeping them close.

    GET    /api/people?q=mira             search adventurers by name (at least 2 letters); each result says
                                          whether they're your friend or a request is waiting
    GET    /api/friends                   your friends, requests you've received and requests you've sent
    POST   /api/friends                   {user_id}   send a friend request (if they already asked you, you're friends)
    POST   /api/friends/<user_id>/accept  accept their request
    DELETE /api/friends/<user_id>         decline their request, cancel yours, or stop being friends

Only names and avatars are ever shown, never emails. Friends can be invited to a party straight from a list
(the DM), or suggested to a party's DM by a member (see joining.py).
"""
from __future__ import annotations

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import or_

from .extensions import db
from .models import Friendship, User, utcnow
from .parties import person
from .security import json_body, login_required, send_email, site_url

bp = Blueprint("friends", __name__, url_prefix="/api")

SEARCH_MIN = 2
SEARCH_LIMIT = 20
MAX_FRIENDS = 200
FRIENDS_PATH = "/play/campaigns/friends"


def _pair(a: User, b_id: int) -> Friendship | None:
    """The one row between two people, whichever of them asked."""
    return db.session.query(Friendship).filter(or_(
        (Friendship.requester_id == a.id) & (Friendship.addressee_id == b_id),
        (Friendship.requester_id == b_id) & (Friendship.addressee_id == a.id),
    )).first()


def _relation(f: Friendship | None, me: User) -> str | None:
    if f is None:
        return None
    if f.status == "accepted":
        return "friend"
    return "sent" if f.requester_id == me.id else "received"


def friends_of(user: User) -> list[User]:
    rows = user.sent_friend_requests + user.received_friend_requests
    return sorted((f.other(user) for f in rows if f.status == "accepted"), key=lambda u: u.name.lower())


def are_friends(a: User, b: User) -> bool:
    f = _pair(a, b.id)
    return f is not None and f.status == "accepted"


def _findable(user: User | None) -> bool:
    return user is not None and user.is_verified and not user.is_banned


def _other(user_id: int) -> User:
    other = db.session.get(User, user_id)
    if not _findable(other) or other.id == g.user.id:
        abort(404, description="No adventurer by that name.")
    return other


@bp.get("/people")
@login_required
def search_people():
    q = (request.args.get("q") or "").strip()
    if len(q) < SEARCH_MIN:
        return jsonify(people=[], min_length=SEARCH_MIN)
    pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    found = (db.session.query(User)
             .filter(User.name.ilike(pattern, escape="\\"), User.id != g.user.id,
                     User.is_verified.is_(True), User.is_banned.is_(False))
             .order_by(User.name, User.id).limit(SEARCH_LIMIT).all())
    return jsonify(people=[{**person(u), "relation": _relation(_pair(g.user, u.id), g.user)} for u in found],
                   min_length=SEARCH_MIN)


@bp.get("/friends")
@login_required
def list_friends():
    me = g.user
    received = [f for f in me.received_friend_requests if f.status == "pending" and _findable(f.requester)]
    sent = [f for f in me.sent_friend_requests if f.status == "pending" and _findable(f.addressee)]

    def asked(f: Friendship, who: User) -> dict:
        return {**person(who), "requested_at": f.created_at.isoformat() + "Z"}

    return jsonify(
        friends=[person(u) for u in friends_of(me) if _findable(u)],
        received=[asked(f, f.requester) for f in sorted(received, key=lambda f: f.id)],
        sent=[asked(f, f.addressee) for f in sorted(sent, key=lambda f: f.id)],
        limit=MAX_FRIENDS,
    )


@bp.post("/friends")
@login_required
def send_request():
    data = json_body()
    try:
        other = _other(int(data.get("user_id")))
    except (TypeError, ValueError):
        abort(400, description="Choose someone to send a friend request to.")
    existing = _pair(g.user, other.id)
    if existing is not None:
        if existing.status == "accepted":
            abort(400, description=f"You and {other.name} are already friends.")
        if existing.requester_id == g.user.id:
            abort(400, description=f"You've already sent {other.name} a friend request.")
        return _accept(existing, other)  # they asked first, so asking back says yes
    if len(friends_of(g.user)) >= MAX_FRIENDS:
        abort(400, description=f"You can have up to {MAX_FRIENDS} friends.")
    db.session.add(Friendship(requester_id=g.user.id, addressee_id=other.id))
    if other.notify_party:
        send_email(other.email, f"{g.user.name} sent you a friend request",
                   f"Greetings {other.name},\n\n{g.user.name} would like to be friends on Tomes of Faerun. "
                   "Open your friends to accept or decline.", site_url(FRIENDS_PATH))
    db.session.commit()
    return jsonify(message=f"Friend request sent to {other.name}.", relation="sent"), 201


def _accept(f: Friendship, other: User):
    f.status = "accepted"
    f.accepted_at = utcnow()
    db.session.commit()
    return jsonify(message=f"You and {other.name} are now friends.", relation="friend")


@bp.post("/friends/<int:user_id>/accept")
@login_required
def accept_request(user_id: int):
    other = _other(user_id)
    f = _pair(g.user, other.id)
    if f is None or f.status != "pending" or f.addressee_id != g.user.id:
        abort(404, description=f"{other.name} hasn't sent you a friend request.")
    return _accept(f, other)


@bp.delete("/friends/<int:user_id>")
@login_required
def remove(user_id: int):
    other = db.session.get(User, user_id)
    f = _pair(g.user, user_id) if other else None
    if f is None:
        abort(404, description="There's no friendship or request to remove.")
    if f.status == "accepted":
        message = f"You and {other.name} are no longer friends."
    elif f.requester_id == g.user.id:
        message = f"Your friend request to {other.name} was cancelled."
    else:
        message = f"You declined {other.name}'s friend request."
    db.session.delete(f)
    db.session.commit()
    return jsonify(message=message, relation=None)
