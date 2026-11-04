"""Parties: the groups of players a Dungeon Master leads.

    GET    /api/parties                         parties you lead, parties you're in, and your invitations
    POST   /api/parties                         {name, description, visibility}   (you become its DM)
    GET    /api/parties/<id>                    the party, its members and its campaigns (DM and members)
    PATCH  /api/parties/<id>                    {name, description, visibility}   (DM only)
    DELETE /api/parties/<id>                    (DM only; its campaigns carry on without a party)
    POST   /api/parties/<id>/invites            {email} or {user_id} of a friend   invite a player (DM only)
    POST   /api/parties/<id>/accept             accept your invitation
    POST   /api/parties/<id>/decline            decline your invitation
    DELETE /api/parties/<id>/members/<user_id>  DM removes a player or cancels an invite; a player can remove themselves

Each party also has a chat (see chat.py); the party lists say how many messages you haven't read.
Public parties show up in the party search, where players ask to join; members can also suggest their
friends. The DM answers those join requests (see joining.py and friends.py).
"""
from __future__ import annotations

from flask import Blueprint, abort, g, jsonify
from .extensions import db
from .models import Party, PartyMember, User, utcnow
from .security import get_user_by_email, json_body, login_required, send_email, site_url, text

bp = Blueprint("parties", __name__, url_prefix="/api/parties")

VISIBILITY = {"private": "Private", "public": "Public"}
MAX_PARTIES = 30
MAX_MEMBERS = 12
NAME_MAX = 60
DESCRIPTION_MAX = 1000


def _invalid(errors: dict[str, str]):
    return jsonify(error="Please fix the highlighted fields.", errors=errors), 400


def person(user: User) -> dict:
    """What other players may see of someone: their name and avatar, never their email."""
    return {"id": user.id, "name": user.name, "avatar_url": f"/uploads/{user.avatar}" if user.avatar else None}


def membership(party: Party, user: User) -> PartyMember | None:
    return next((m for m in party.members if m.user_id == user.id), None)


def is_member(party: Party | None, user: User) -> bool:
    m = membership(party, user) if party else None
    return m is not None and m.status == "member"


def _party(party_id: int) -> Party:
    party = db.session.get(Party, party_id)
    if party is None:
        abort(404, description="Party not found.")
    return party


def _led(party_id: int) -> Party:
    """A party the current user is the DM of. Members get 403, strangers 404."""
    party = _party(party_id)
    if party.dm_id == g.user.id:
        return party
    if membership(party, g.user):
        abort(403, description="Only the party's Dungeon Master can do that.")
    abort(404, description="Party not found.")


def _summary(party: Party) -> dict:
    members = [m for m in party.members if m.status == "member"]
    return {
        "id": party.id, "name": party.name, "description": party.description,
        "visibility": party.visibility, "dm": person(party.dm),
        "member_count": len(members),
        "invited_count": len(party.members) - len(members),
        "campaigns": [{"id": c.id, "name": c.name, "status": c.status} for c in party.campaigns],
        "created_at": party.created_at.isoformat() + "Z",
    }


def _member_dict(m: PartyMember, show_email: bool) -> dict:
    return {
        **person(m.user), **({"email": m.user.email} if show_email else {}),
        "status": m.status,
        "invited_at": m.invited_at.isoformat() + "Z",
        "joined_at": m.joined_at.isoformat() + "Z" if m.joined_at else None,
    }


def _detail(party: Party) -> dict:
    from .friends import friends_of
    from .joining import request_dict

    is_dm = party.dm_id == g.user.id
    # Members only see who's in; the DM also sees who's still invited (and the emails they typed).
    members = [m for m in party.members if is_dm or m.status == "member"]
    # Friends who aren't in the party, invited or waiting on a request: the DM can invite them,
    # and a member can suggest them to the DM.
    taken = {m.user_id for m in party.members} | {r.user_id for r in party.join_requests} | {party.dm_id}
    friends = [person(u) for u in friends_of(g.user) if u.id not in taken and u.is_verified and not u.is_banned]
    detail = {**_summary(party), "role": "dm" if is_dm else "player",
              "members": [_member_dict(m, is_dm) for m in members], "friends": friends}
    if is_dm:
        detail["requests"] = [request_dict(r) for r in party.join_requests]
    else:
        detail["suggestions"] = [request_dict(r) for r in party.join_requests if r.suggested_by_id == g.user.id]
    return {"party": detail}


def _fields(data: dict, current: Party | None = None) -> tuple[dict, dict]:
    values: dict = {}
    errors: dict[str, str] = {}
    if current is None or "name" in data:
        name = text(data, "name")
        if not name:
            errors["name"] = "Give the party a name."
        elif len(name) > NAME_MAX:
            errors["name"] = f"Keep the name to {NAME_MAX} characters or fewer."
        elif any(p.name.lower() == name.lower() and p is not current for p in g.user.parties):
            errors["name"] = "You already lead a party with that name."
        values["name"] = name
    if "description" in data:
        description = str(data.get("description") or "").strip()
        if len(description) > DESCRIPTION_MAX:
            errors["description"] = f"Keep the description to {DESCRIPTION_MAX} characters or fewer."
        values["description"] = description
    if current is None or "visibility" in data:
        visibility = data.get("visibility", "private")
        if visibility not in VISIBILITY:
            errors["visibility"] = "Choose public or private."
        values["visibility"] = visibility
    return values, errors


@bp.get("")
@login_required
def list_parties():
    led = sorted(g.user.parties, key=lambda p: p.name.lower())
    joined = [m.party for m in g.user.memberships if m.status == "member"]
    invites = [m for m in g.user.memberships if m.status == "invited"]
    from .chat import unread_count

    def with_unread(p: Party) -> dict:
        return {**_summary(p), "unread": unread_count(p, g.user)}

    return jsonify(
        led=[{**with_unread(p), "request_count": len(p.join_requests)} for p in led],
        joined=[with_unread(p) for p in sorted(joined, key=lambda p: p.name.lower())],
        invitations=[{**_summary(m.party), "invited_at": m.invited_at.isoformat() + "Z"} for m in invites],
        limit=MAX_PARTIES,
    )


@bp.post("")
@login_required
def create_party():
    if len(g.user.parties) >= MAX_PARTIES:
        abort(400, description=f"You can lead up to {MAX_PARTIES} parties. Disband one to make room.")
    values, errors = _fields(json_body())
    if errors:
        return _invalid(errors)
    party = Party(dm_id=g.user.id, **values)
    db.session.add(party)
    db.session.commit()
    return jsonify(_detail(party)), 201


@bp.get("/<int:party_id>")
@login_required
def get_party(party_id: int):
    party = _party(party_id)
    if party.dm_id != g.user.id and membership(party, g.user) is None:
        abort(404, description="Party not found.")
    return jsonify(_detail(party))


@bp.patch("/<int:party_id>")
@login_required
def update_party(party_id: int):
    party = _led(party_id)
    values, errors = _fields(json_body(), party)
    if errors:
        return _invalid(errors)
    for key, value in values.items():
        setattr(party, key, value)
    db.session.commit()
    return jsonify(_detail(party))


@bp.delete("/<int:party_id>")
@login_required
def delete_party(party_id: int):
    party = _led(party_id)
    for campaign in party.campaigns:
        campaign.party_id = None
    db.session.delete(party)
    db.session.commit()
    return jsonify(message=f"{party.name} was disbanded. Its campaigns carry on without a party.")


@bp.post("/<int:party_id>/invites")
@login_required
def invite(party_id: int):
    party = _led(party_id)
    data = json_body()
    field = "user_id" if data.get("user_id") is not None else "email"
    if field == "user_id":
        # Inviting one of your friends from the list: no email needed.
        from .friends import are_friends
        try:
            user = db.session.get(User, int(data["user_id"]))
        except (TypeError, ValueError):
            user = None
        if user is None or user.is_banned or not are_friends(g.user, user):
            return _invalid({"user_id": "Choose one of your friends."})
    else:
        email = text(data, "email").lower()
        if not email:
            return _invalid({"email": "Type the email address the player signed up with."})
        if email == g.user.email:
            return _invalid({"email": "You're the party's Dungeon Master, so you don't need an invitation."})
        user = get_user_by_email(email)
        if user is None or not user.is_verified or user.is_banned:
            return _invalid({"email": "No adventurer has signed up with that email."})
    existing = membership(party, user)
    if existing is not None:
        already = "is already in the party" if existing.status == "member" else "has already been invited"
        return _invalid({field: f"{user.name} {already}."})
    if len(party.members) >= MAX_MEMBERS:
        abort(400, description=f"A party has room for {MAX_MEMBERS} players, counting open invitations.")
    party.members.append(PartyMember(user_id=user.id))
    # Inviting someone answers any request to join that was waiting for them.
    for r in [r for r in party.join_requests if r.user_id == user.id]:
        party.join_requests.remove(r)
    if user.notify_party:
        send_email(user.email, f"{g.user.name} invited you to join {party.name}",
                   f"Greetings {user.name},\n\n{g.user.name} has invited you to join the party "
                   f"“{party.name}”. Open your parties to accept or decline.",
                   site_url("/play/campaigns/parties"))
    db.session.commit()
    return jsonify(message=f"{user.name} was invited to {party.name}.", **_detail(party)), 201


def _my_invitation(party: Party) -> PartyMember:
    m = membership(party, g.user)
    if m is None or m.status != "invited":
        abort(404, description="You don't have an invitation to that party.")
    return m


@bp.post("/<int:party_id>/accept")
@login_required
def accept(party_id: int):
    party = _party(party_id)
    m = _my_invitation(party)
    m.status = "member"
    m.joined_at = utcnow()
    db.session.commit()
    return jsonify(message=f"You joined {party.name}.", **_detail(party))


@bp.post("/<int:party_id>/decline")
@login_required
def decline(party_id: int):
    party = _party(party_id)
    party.members.remove(_my_invitation(party))
    db.session.commit()
    return jsonify(message=f"You declined the invitation to {party.name}.")


@bp.delete("/<int:party_id>/members/<int:user_id>")
@login_required
def remove_member(party_id: int, user_id: int):
    party = _party(party_id)
    leaving = user_id == g.user.id
    if not leaving:
        party = _led(party_id)
    m = next((m for m in party.members if m.user_id == user_id), None)
    if m is None:
        abort(404, description="That player isn't in the party.")
    name = m.user.name
    was_invite = m.status == "invited"
    # Their characters' campaign instances are kept (hidden), so nothing is lost if they come back.
    party.members.remove(m)
    db.session.commit()
    if leaving:
        return jsonify(message=f"You left {party.name}.")
    message = f"{name}'s invitation was cancelled." if was_invite else f"{name} was removed from {party.name}."
    return jsonify(message=message, **_detail(party))
