"""Campaigns: run by a Dungeon Master, played by the members of the party attached to them.

    GET    /api/campaigns                           campaigns you run and campaigns you play in
    POST   /api/campaigns                           {name, description, status}
    GET    /api/campaigns/<id>                      the campaign as the DM or a player sees it
    PATCH  /api/campaigns/<id>                      {name, description, status, dm_notes, party_id}   (DM)
    DELETE /api/campaigns/<id>                      (DM)

    POST   /api/campaigns/<id>/sessions             {played_on, title, summary}   (DM)
    PATCH  /api/campaigns/<id>/sessions/<sid>       (DM)
    DELETE /api/campaigns/<id>/sessions/<sid>       (DM)

    PUT    /api/campaigns/<id>/encounters/<collection_id>   attach one of your bestiary collections (DM)
    DELETE /api/campaigns/<id>/encounters/<collection_id>   take it off again (DM)

    POST   /api/campaigns/<id>/instance             {character_id}  bring one of your characters (party members)
    GET    /api/campaigns/<id>/instance             your character as it stands in this campaign
    PATCH  /api/campaigns/<id>/instance             {build, build_mode, current_hp, temp_hp}
    DELETE /api/campaigns/<id>/instance             take your character out of the campaign
    GET    /api/campaigns/<id>/instances/<iid>      a player's character, read-only (DM)
    PUT    /api/campaigns/<id>/instances/<iid>/note {note}  the DM's note on it, which the player sees

    GET    /api/campaigns/characters/<character_id> the campaigns one of your characters is in

Who sees what (from the plan): the overview and session log are for everyone at the table; the
encounters and DM notes are the DM's alone. Players manage their own instance; the DM may read it
and leave a note, but can't change it.
"""
from __future__ import annotations

import copy
from datetime import date

from flask import Blueprint, abort, g, jsonify
from sqlalchemy import select

from .characters import engine
from .extensions import db
from .models import (Campaign, CampaignEncounter, Character, CharacterInstance, MonsterCollection, Party,
                     SessionEntry, utcnow)
from .bestiary import _collection_summary
from .parties import is_member, person
from .security import json_body, login_required, text

bp = Blueprint("campaigns", __name__, url_prefix="/api/campaigns")

STATUSES = {"planning": "Planning", "active": "Active", "finished": "Finished"}
MAX_CAMPAIGNS = 30
MAX_SESSIONS = 500
MAX_ENCOUNTERS = 50
NAME_MAX = 80
DESCRIPTION_MAX = 4000
DM_NOTES_MAX = 10000
SESSION_TITLE_MAX = 100
SESSION_SUMMARY_MAX = 5000
INSTANCE_NOTE_MAX = 2000


def _invalid(errors: dict[str, str]):
    return jsonify(error="Please fix the highlighted fields.", errors=errors), 400


def _iso(d) -> str:
    return d.isoformat() + "Z"


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------
def _campaign(campaign_id: int) -> Campaign:
    campaign = db.session.get(Campaign, campaign_id)
    if campaign is None:
        abort(404, description="Campaign not found.")
    return campaign


def _is_dm(campaign: Campaign) -> bool:
    return campaign.dm_id == g.user.id


def _is_player(campaign: Campaign) -> bool:
    return is_member(campaign.party, g.user)


def _visible(campaign_id: int) -> Campaign:
    """A campaign you run or play in. Everyone else gets 404, so they can't tell it exists."""
    campaign = _campaign(campaign_id)
    if not (_is_dm(campaign) or _is_player(campaign)):
        abort(404, description="Campaign not found.")
    return campaign


def _run(campaign_id: int) -> Campaign:
    """A campaign you're the Dungeon Master of. Its players get 403."""
    campaign = _visible(campaign_id)
    if not _is_dm(campaign):
        abort(403, description="Only the campaign's Dungeon Master can do that.")
    return campaign


def _players(campaign: Campaign) -> list:
    return [m for m in campaign.party.members if m.status == "member"] if campaign.party else []


def _current_instances(campaign: Campaign) -> list[CharacterInstance]:
    """Instances of players who are in the party right now (a player who left keeps theirs, hidden)."""
    ids = {m.user_id for m in _players(campaign)}
    return [i for i in campaign.instances if i.user_id in ids]


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------
def _instance_summary(i: CharacterInstance) -> dict:
    b = i.build
    max_hp = engine.check(b, build_mode=i.build_mode, previous_level=b.get("level", 1))["sheet"]["hit_points"]
    return {
        "id": i.id, "name": i.name, "player": person(i.user),
        "character_id": i.character_id,
        "level": b.get("level", 1),
        "race": engine.name_of("subraces", b.get("subrace")) or engine.name_of("races", b.get("race")),
        "class": engine.name_of("classes", b.get("class")),
        "subclass": engine.name_of("subclasses", b.get("subclass")),
        "build_mode": i.build_mode,
        "max_hp": max_hp,
        "current_hp": max_hp if i.current_hp is None else min(i.current_hp, max_hp),
        "temp_hp": i.temp_hp,
        "dm_note": i.dm_note,
        "updated_at": _iso(i.updated_at),
    }


def _summary(c: Campaign) -> dict:
    return {
        "id": c.id, "name": c.name, "description": c.description,
        "status": c.status, "status_label": STATUSES[c.status],
        "dm": person(c.dm),
        "party": {"id": c.party.id, "name": c.party.name} if c.party else None,
        "player_count": len(_players(c)),
        "session_count": len(c.sessions),
        "last_played": c.sessions[0].played_on.isoformat() if c.sessions else None,
        "created_at": _iso(c.created_at), "updated_at": _iso(c.updated_at),
    }


def _session_dict(s: SessionEntry) -> dict:
    return {"id": s.id, "played_on": s.played_on.isoformat(), "title": s.title, "summary": s.summary}


def _encounter_dict(e: CampaignEncounter) -> dict:
    return {"id": e.id, "attached_at": _iso(e.created_at), "collection": _collection_summary(e.collection)}


def _detail(c: Campaign) -> dict:
    dm = _is_dm(c)
    instances = _current_instances(c)
    mine = next((i for i in c.instances if i.user_id == g.user.id), None)
    players = []
    for m in _players(c):
        inst = next((i for i in instances if i.user_id == m.user_id), None)
        players.append({**person(m.user), "instance": _instance_summary(inst) if inst and (dm or inst is mine) else
                        ({"id": inst.id, "name": inst.name, "level": inst.build.get("level", 1),
                          "class": engine.name_of("classes", inst.build.get("class"))} if inst else None)})
    body = {
        **_summary(c),
        "role": "dm" if dm else "player",
        "players": players,
        "sessions": [_session_dict(s) for s in c.sessions],
        "my_instance": _instance_summary(mine) if mine and not dm else None,
    }
    if dm:
        body["dm_notes"] = c.dm_notes
        body["encounters"] = [_encounter_dict(e) for e in c.encounters]
    return {"campaign": body}


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------
@bp.get("/options")
def options():
    return jsonify(statuses=[{"value": k, "label": v} for k, v in STATUSES.items()],
                   max_campaigns=MAX_CAMPAIGNS)


def _fields(data: dict, current: Campaign | None = None) -> tuple[dict, dict]:
    values: dict = {}
    errors: dict[str, str] = {}
    if current is None or "name" in data:
        name = text(data, "name")
        if not name:
            errors["name"] = "Give the campaign a name."
        elif len(name) > NAME_MAX:
            errors["name"] = f"Keep the name to {NAME_MAX} characters or fewer."
        elif any(c.name.lower() == name.lower() and c is not current for c in g.user.campaigns):
            errors["name"] = "You already run a campaign with that name."
        values["name"] = name
    if "description" in data:
        description = str(data.get("description") or "").strip()
        if len(description) > DESCRIPTION_MAX:
            errors["description"] = f"Keep the description to {DESCRIPTION_MAX} characters or fewer."
        values["description"] = description
    if current is None or "status" in data:
        status = data.get("status", "planning")
        if status not in STATUSES:
            errors["status"] = "Status must be Planning, Active or Finished."
        values["status"] = status
    if "dm_notes" in data:
        notes = str(data.get("dm_notes") or "")
        if len(notes) > DM_NOTES_MAX:
            errors["dm_notes"] = f"Keep the notes to {DM_NOTES_MAX} characters or fewer."
        values["dm_notes"] = notes
    if "party_id" in data:
        party_id = data["party_id"]
        if party_id is None:
            values["party_id"] = None
        else:
            party = db.session.get(Party, party_id) if isinstance(party_id, int) and not isinstance(party_id, bool) else None
            if party is None or party.dm_id != g.user.id:
                errors["party_id"] = "Choose one of the parties you lead."
            else:
                values["party_id"] = party.id
    return values, errors


@bp.get("")
@login_required
def list_campaigns():
    running = sorted(g.user.campaigns, key=lambda c: (list(STATUSES).index(c.status), c.name.lower()))
    party_ids = [m.party_id for m in g.user.memberships if m.status == "member"]
    playing = list(db.session.scalars(
        select(Campaign).where(Campaign.party_id.in_(party_ids)).order_by(Campaign.name))) if party_ids else []
    mine = {i.campaign_id: i for i in g.user.instances}
    return jsonify(
        running=[_summary(c) for c in running],
        playing=[{**_summary(c), "my_instance": _instance_summary(mine[c.id]) if c.id in mine else None}
                 for c in playing if c.dm_id != g.user.id],
        limit=MAX_CAMPAIGNS,
    )


@bp.post("")
@login_required
def create_campaign():
    if len(g.user.campaigns) >= MAX_CAMPAIGNS:
        abort(400, description=f"You can run up to {MAX_CAMPAIGNS} campaigns. Delete one to make room.")
    values, errors = _fields(json_body())
    if errors:
        return _invalid(errors)
    campaign = Campaign(dm_id=g.user.id, **values)
    db.session.add(campaign)
    db.session.commit()
    return jsonify(_detail(campaign)), 201


@bp.get("/<int:campaign_id>")
@login_required
def get_campaign(campaign_id: int):
    return jsonify(_detail(_visible(campaign_id)))


@bp.patch("/<int:campaign_id>")
@login_required
def update_campaign(campaign_id: int):
    campaign = _run(campaign_id)
    values, errors = _fields(json_body(), campaign)
    if errors:
        return _invalid(errors)
    for key, value in values.items():
        setattr(campaign, key, value)
    campaign.updated_at = utcnow()
    db.session.commit()
    db.session.refresh(campaign)
    return jsonify(_detail(campaign))


@bp.delete("/<int:campaign_id>")
@login_required
def delete_campaign(campaign_id: int):
    campaign = _run(campaign_id)
    db.session.delete(campaign)
    db.session.commit()
    return jsonify(message=f"{campaign.name} was deleted.")


# ---------------------------------------------------------------------------
# Session log
# ---------------------------------------------------------------------------
def _session_fields(data: dict, partial: bool) -> tuple[dict, dict]:
    values: dict = {}
    errors: dict[str, str] = {}
    if not partial or "played_on" in data:
        try:
            values["played_on"] = date.fromisoformat(str(data.get("played_on") or ""))
        except ValueError:
            errors["played_on"] = "Pick the date the session was played."
    if not partial or "title" in data:
        title = text(data, "title")
        if not title:
            errors["title"] = "Give the session a title."
        elif len(title) > SESSION_TITLE_MAX:
            errors["title"] = f"Keep the title to {SESSION_TITLE_MAX} characters or fewer."
        values["title"] = title
    if not partial or "summary" in data:
        summary = str(data.get("summary") or "").strip()
        if len(summary) > SESSION_SUMMARY_MAX:
            errors["summary"] = f"Keep the summary to {SESSION_SUMMARY_MAX} characters or fewer."
        values["summary"] = summary
    return values, errors


def _owned_session(campaign: Campaign, session_id: int) -> SessionEntry:
    entry = next((s for s in campaign.sessions if s.id == session_id), None)
    if entry is None:
        abort(404, description="That session isn't in this campaign's log.")
    return entry


def _touch(campaign: Campaign) -> dict:
    campaign.updated_at = utcnow()
    db.session.commit()
    db.session.expire(campaign)
    return _detail(campaign)


@bp.post("/<int:campaign_id>/sessions")
@login_required
def add_session(campaign_id: int):
    campaign = _run(campaign_id)
    if len(campaign.sessions) >= MAX_SESSIONS:
        abort(400, description=f"A session log holds up to {MAX_SESSIONS} entries.")
    values, errors = _session_fields(json_body(), partial=False)
    if errors:
        return _invalid(errors)
    campaign.sessions.append(SessionEntry(**values))
    return jsonify(message=f"“{values['title']}” was added to the session log.", **_touch(campaign)), 201


@bp.patch("/<int:campaign_id>/sessions/<int:session_id>")
@login_required
def update_session(campaign_id: int, session_id: int):
    campaign = _run(campaign_id)
    entry = _owned_session(campaign, session_id)
    values, errors = _session_fields(json_body(), partial=True)
    if errors:
        return _invalid(errors)
    for key, value in values.items():
        setattr(entry, key, value)
    return jsonify(_touch(campaign))


@bp.delete("/<int:campaign_id>/sessions/<int:session_id>")
@login_required
def delete_session(campaign_id: int, session_id: int):
    campaign = _run(campaign_id)
    entry = _owned_session(campaign, session_id)
    campaign.sessions.remove(entry)
    return jsonify(message=f"“{entry.title}” was taken out of the log.", **_touch(campaign))


# ---------------------------------------------------------------------------
# Encounters (bestiary collections)
# ---------------------------------------------------------------------------
def _my_collection(collection_id: int) -> MonsterCollection:
    collection = db.session.get(MonsterCollection, collection_id)
    if collection is None or collection.user_id != g.user.id:
        abort(404, description="Collection not found.")
    return collection


@bp.put("/<int:campaign_id>/encounters/<int:collection_id>")
@login_required
def attach_collection(campaign_id: int, collection_id: int):
    campaign = _run(campaign_id)
    collection = _my_collection(collection_id)
    if any(e.collection_id == collection.id for e in campaign.encounters):
        return jsonify(message=f"{collection.name} is already one of {campaign.name}'s encounters.", **_detail(campaign))
    if len(campaign.encounters) >= MAX_ENCOUNTERS:
        abort(400, description=f"A campaign holds up to {MAX_ENCOUNTERS} encounters.")
    campaign.encounters.append(CampaignEncounter(collection_id=collection.id))
    return jsonify(message=f"{collection.name} was added to {campaign.name}'s encounters.", **_touch(campaign)), 201


@bp.delete("/<int:campaign_id>/encounters/<int:collection_id>")
@login_required
def detach_collection(campaign_id: int, collection_id: int):
    campaign = _run(campaign_id)
    link = next((e for e in campaign.encounters if e.collection_id == collection_id), None)
    if link is None:
        abort(404, description="That collection isn't one of this campaign's encounters.")
    name = link.collection.name
    campaign.encounters.remove(link)
    return jsonify(message=f"{name} was taken off {campaign.name}. The collection is still in your bestiary.",
                   **_touch(campaign))


# ---------------------------------------------------------------------------
# Character instances
# ---------------------------------------------------------------------------
def _instance_detail(i: CharacterInstance) -> dict:
    result = engine.check(i.build, build_mode=i.build_mode, previous_level=i.build.get("level", 1))
    return {"instance": {**_instance_summary(i), "build": i.build,
                         "campaign": {"id": i.campaign.id, "name": i.campaign.name},
                         "base_character": i.character.to_dict() if i.character else None},
            **result}


def _my_instance(campaign: Campaign) -> CharacterInstance:
    instance = next((i for i in campaign.instances if i.user_id == g.user.id), None)
    if instance is None:
        abort(404, description="You haven't brought a character to this campaign yet.")
    return instance


def _as_player(campaign_id: int) -> Campaign:
    campaign = _visible(campaign_id)
    if not _is_player(campaign):
        abort(403, description="Only players in the campaign's party bring characters to it.")
    return campaign


@bp.post("/<int:campaign_id>/instance")
@login_required
def join_with_character(campaign_id: int):
    campaign = _as_player(campaign_id)
    data = json_body()
    character = db.session.get(Character, data.get("character_id")) if isinstance(data.get("character_id"), int) else None
    if character is None or character.user_id != g.user.id:
        return _invalid({"character_id": "Choose one of your characters."})
    if not character.is_complete:
        return _invalid({"character_id": f"{character.name} is still a draft. Finish it in the Character Manager first."})
    existing = next((i for i in campaign.instances if i.user_id == g.user.id), None)
    if existing is not None:
        abort(409, description=f"You're already playing {existing.name} in {campaign.name}.")
    instance = CharacterInstance(
        campaign_id=campaign.id, user_id=g.user.id, character_id=character.id, name=character.name,
        build=copy.deepcopy(character.build), build_mode=character.build_mode, is_complete=True,
    )
    db.session.add(instance)
    db.session.commit()
    return jsonify(message=f"{character.name} joined {campaign.name}.", **_instance_detail(instance)), 201


@bp.get("/<int:campaign_id>/instance")
@login_required
def my_instance(campaign_id: int):
    return jsonify(_instance_detail(_my_instance(_as_player(campaign_id))))


def _hp(data: dict, key: str, high: int) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= high:
        abort(400, description=f"{'Hit points' if key == 'current_hp' else 'Temporary hit points'} "
                               f"must be a whole number from 0 to {high}.")
    return value


@bp.patch("/<int:campaign_id>/instance")
@login_required
def update_instance(campaign_id: int):
    instance = _my_instance(_as_player(campaign_id))
    data = json_body()
    if "build" in data or "build_mode" in data:
        build = data.get("build", instance.build)
        if not isinstance(build, dict) or ("choices" in build and not isinstance(build["choices"], dict)):
            abort(400, description="Send the character's build as an object.")
        mode = data.get("build_mode", instance.build_mode)
        if mode not in engine.BUILD_MODES:
            abort(400, description="Build mode must be “easy” or “standard”.")
        cleaned = engine.clean(build)
        # Easy build's level cap is for creating characters; an instance can keep levelling.
        result = engine.check(cleaned, build_mode="standard")
        if not result["valid"]:
            return jsonify(error="That build breaks the rules.", errors=result["errors"]), 400
        if not result["complete"]:
            return jsonify(error="Finish every choice before saving: a character in a campaign can't be a draft.",
                           errors=result["missing"]), 400
        instance.build = cleaned
        instance.name = cleaned["name"] or instance.name
        instance.build_mode = mode
    max_hp = engine.check(instance.build)["sheet"]["hit_points"]
    if "current_hp" in data:
        instance.current_hp = _hp(data, "current_hp", max_hp)
    if "temp_hp" in data:
        instance.temp_hp = _hp(data, "temp_hp", 999)
    instance.updated_at = utcnow()
    db.session.commit()
    return jsonify(_instance_detail(instance))


@bp.delete("/<int:campaign_id>/instance")
@login_required
def leave_with_character(campaign_id: int):
    campaign = _as_player(campaign_id)
    instance = _my_instance(campaign)
    db.session.delete(instance)
    db.session.commit()
    return jsonify(message=f"{instance.name} left {campaign.name}. Your character in the Character Manager is unchanged.")


def _players_instance(campaign: Campaign, instance_id: int) -> CharacterInstance:
    instance = next((i for i in _current_instances(campaign) if i.id == instance_id), None)
    if instance is None:
        abort(404, description="That character isn't in this campaign.")
    return instance


@bp.get("/<int:campaign_id>/instances/<int:instance_id>")
@login_required
def view_instance(campaign_id: int, instance_id: int):
    campaign = _visible(campaign_id)
    instance = _players_instance(campaign, instance_id)
    if not _is_dm(campaign) and instance.user_id != g.user.id:
        abort(403, description="Only the Dungeon Master can read other players' characters.")
    return jsonify(_instance_detail(instance))


@bp.put("/<int:campaign_id>/instances/<int:instance_id>/note")
@login_required
def set_instance_note(campaign_id: int, instance_id: int):
    campaign = _run(campaign_id)
    instance = _players_instance(campaign, instance_id)
    note = str(json_body().get("note") or "").strip()
    if len(note) > INSTANCE_NOTE_MAX:
        return _invalid({"note": f"Keep the note to {INSTANCE_NOTE_MAX} characters or fewer."})
    instance.dm_note = note
    db.session.commit()
    return jsonify(message=f"Your note on {instance.name} was saved.", **_instance_detail(instance))


# ---------------------------------------------------------------------------
# A base character's campaigns (Character Manager › Campaigns)
# ---------------------------------------------------------------------------
@bp.get("/characters/<int:character_id>")
@login_required
def character_campaigns(character_id: int):
    character = db.session.get(Character, character_id)
    if character is None or character.user_id != g.user.id:
        abort(404, description="Character not found.")
    return jsonify(campaigns=[
        {"campaign": {"id": i.campaign.id, "name": i.campaign.name, "status": i.campaign.status,
                      "status_label": STATUSES[i.campaign.status], "dm": person(i.campaign.dm),
                      "in_party": _is_player(i.campaign)},
         "instance": _instance_summary(i)}
        for i in sorted(character.instances, key=lambda i: i.campaign.name.lower())
    ])
