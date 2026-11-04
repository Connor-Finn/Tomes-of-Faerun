"""Joining parties: public parties anyone can ask to join, and friends that members suggest.

    GET    /api/parties/public?q=lantern                  public parties (not ones you lead), and where you stand with each
    GET    /api/parties/requests                          join requests waiting on you, for every party you lead
    POST   /api/parties/<id>/requests                     {message}   ask to join a public party
                                                          {user_id}   a member suggests one of their friends (any party)
    POST   /api/parties/<id>/requests/<request_id>/accept the DM says yes
    DELETE /api/parties/<id>/requests/<request_id>        the DM says no, or whoever asked withdraws it

The Dungeon Master always decides. Someone who asked for themselves joins as soon as the DM says yes.
A suggested friend didn't ask, so saying yes sends them an invitation they can accept or decline.
The DM gets an email for each new request when they've turned on party emails.
"""
from __future__ import annotations

from flask import Blueprint, abort, g, jsonify, request

from .extensions import db
from .friends import are_friends
from .models import JoinRequest, Party, PartyMember, User, utcnow
from .parties import MAX_MEMBERS, _detail, _party, _summary, membership, person
from .security import json_body, login_required, send_email, site_url

bp = Blueprint("joining", __name__, url_prefix="/api/parties")

MESSAGE_MAX = 300
PUBLIC_LIMIT = 50
REQUESTS_PATH = "/dm/campaigns/requests"


def request_dict(r: JoinRequest) -> dict:
    return {
        "id": r.id,
        "party": {"id": r.party.id, "name": r.party.name},
        "person": person(r.user),
        "suggested_by": person(r.suggested_by) if r.suggested_by else None,
        "message": r.message,
        "created_at": r.created_at.isoformat() + "Z",
    }


def pending_request(party: Party, user: User) -> JoinRequest | None:
    return next((r for r in party.join_requests if r.user_id == user.id), None)


def _standing(party: Party, user: User) -> dict:
    """Where you stand with a party you might join."""
    m = membership(party, user)
    if m is not None:
        return {"standing": "member" if m.status == "member" else "invited"}
    r = pending_request(party, user)
    if r is not None:
        return {"standing": "requested", "request_id": r.id}
    return {"standing": None}


def _full(party: Party) -> bool:
    return len(party.members) >= MAX_MEMBERS


@bp.get("/public")
@login_required
def public_parties():
    q = (request.args.get("q") or "").strip().lower()
    parties = (db.session.query(Party).join(User, Party.dm_id == User.id)
               .filter(Party.visibility == "public", Party.dm_id != g.user.id, User.is_banned.is_(False))
               .order_by(Party.name, Party.id).all())
    if q:
        parties = [p for p in parties if q in p.name.lower() or q in p.description.lower() or q in p.dm.name.lower()]
    return jsonify(parties=[{**_summary(p), **_standing(p, g.user), "full": _full(p)} for p in parties[:PUBLIC_LIMIT]])


@bp.get("/requests")
@login_required
def requests_for_me():
    waiting = [r for p in g.user.parties for r in p.join_requests]
    waiting.sort(key=lambda r: r.id)
    return jsonify(requests=[request_dict(r) for r in waiting])


def _notify_dm(party: Party, r: JoinRequest) -> None:
    dm = party.dm
    if not dm.notify_party:
        return
    if r.suggested_by:
        line = f"{r.suggested_by.name} suggested their friend {r.user.name} for “{party.name}”."
    else:
        line = f"{r.user.name} asked to join “{party.name}”."
    send_email(dm.email, f"A join request for {party.name}",
               f"Greetings {dm.name},\n\n{line} Open your join requests to say yes or no.", site_url(REQUESTS_PATH))


@bp.post("/<int:party_id>/requests")
@login_required
def ask(party_id: int):
    party = _party(party_id)
    data = request.get_json(silent=True) or {}  # asking needs no note, so an empty body is fine
    if not isinstance(data, dict):
        data = json_body()  # refuses it
    message = str(data.get("message") or "").strip()
    if len(message) > MESSAGE_MAX:
        return jsonify(error="Please fix the highlighted fields.",
                       errors={"message": f"Keep your note to {MESSAGE_MAX} characters or fewer."}), 400

    if data.get("user_id") is None:
        # Asking for yourself: only public parties take requests from strangers.
        who, suggested_by = g.user, None
        if party.dm_id == g.user.id:
            abort(400, description="You lead this party already.")
        if party.visibility != "public" and membership(party, g.user) is None:
            abort(404, description="Party not found.")
    else:
        # A member suggesting a friend. The DM invites people directly instead.
        if party.dm_id == g.user.id:
            abort(400, description="You're the Dungeon Master: invite them from the party page instead.")
        mine = membership(party, g.user)
        if mine is None or mine.status != "member":
            abort(404, description="Party not found.")
        try:
            who = db.session.get(User, int(data["user_id"]))
        except (TypeError, ValueError):
            who = None
        if who is None or not are_friends(g.user, who) or who.is_banned:
            return jsonify(error="Please fix the highlighted fields.",
                           errors={"user_id": "Choose one of your friends."}), 400
        suggested_by = g.user

    if who.id == party.dm_id:
        abort(400, description=f"{who.name} is the party's Dungeon Master.")
    m = membership(party, who)
    if m is not None:
        you = who.id == g.user.id
        if m.status == "member":
            abort(400, description="You're already in this party." if you else f"{who.name} is already in the party.")
        abort(400, description="You've already been invited: accept it from your parties." if you
              else f"{who.name} has already been invited.")
    if pending_request(party, who) is not None:
        abort(400, description="You've already asked to join." if who.id == g.user.id
              else f"{who.name} has already been suggested.")
    if _full(party):
        abort(400, description=f"{party.name} is full: a party has room for {MAX_MEMBERS} players.")

    r = JoinRequest(party=party, user=who, suggested_by=suggested_by, message=message)
    db.session.add(r)
    _notify_dm(party, r)
    db.session.commit()
    if suggested_by:
        text = f"You suggested {who.name}. {party.dm.name} will decide."
    else:
        text = f"You asked to join {party.name}. {party.dm.name} will decide."
    return jsonify(message=text, request=request_dict(r)), 201


def _request(party: Party, request_id: int) -> JoinRequest:
    r = next((r for r in party.join_requests if r.id == request_id), None)
    if r is None:
        abort(404, description="That request has already been answered or withdrawn.")
    return r


@bp.post("/<int:party_id>/requests/<int:request_id>/accept")
@login_required
def accept(party_id: int, request_id: int):
    party = _party(party_id)
    if party.dm_id != g.user.id:
        abort(404, description="Party not found.")
    r = _request(party, request_id)
    if _full(party):
        abort(400, description=f"{party.name} is full: remove someone or cancel an invitation first.")
    who = r.user
    if r.suggested_by_id is None:
        party.members.append(PartyMember(user_id=who.id, status="member", joined_at=utcnow()))
        message = f"{who.name} joined {party.name}."
    else:
        party.members.append(PartyMember(user_id=who.id))
        message = f"{who.name} was invited to {party.name}."
        if who.notify_party:
            send_email(who.email, f"{g.user.name} invited you to join {party.name}",
                       f"Greetings {who.name},\n\n{g.user.name} has invited you to join the party "
                       f"“{party.name}”. Open your parties to accept or decline.",
                       site_url("/play/campaigns/parties"))
    party.join_requests.remove(r)
    db.session.commit()
    return jsonify(message=message, **_detail(party))


@bp.delete("/<int:party_id>/requests/<int:request_id>")
@login_required
def refuse(party_id: int, request_id: int):
    party = _party(party_id)
    r = _request(party, request_id)
    is_dm = party.dm_id == g.user.id
    if not is_dm and g.user.id not in (r.user_id, r.suggested_by_id):
        abort(404, description="That request has already been answered or withdrawn.")
    name = r.user.name
    party.join_requests.remove(r)
    db.session.commit()
    if is_dm:
        return jsonify(message=f"You turned down {name}'s request.", **_detail(party))
    if r.user_id == g.user.id:
        return jsonify(message=f"You withdrew your request to join {party.name}.")
    return jsonify(message=f"You withdrew your suggestion of {name}.")
