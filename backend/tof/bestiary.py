"""The Bestiary: a Dungeon Master's own collections and environments of SRD monsters.

    GET    /api/bestiary/monsters                       the SRD monsters, plus ?environment=<id>
    GET    /api/bestiary/monsters/<index>               one stat block, and where you've saved it
    GET    /api/bestiary/options                        roles and limits for the forms

    GET    /api/bestiary/collections                    your collections
    POST   /api/bestiary/collections                    {name, notes}
    GET    /api/bestiary/collections/<id>               the collection and its monsters
    PATCH  /api/bestiary/collections/<id>               {name, notes}
    DELETE /api/bestiary/collections/<id>
    POST   /api/bestiary/collections/<id>/monsters      {monster, role, count, note}
    PATCH  /api/bestiary/collections/<id>/monsters/<entry_id>   {role, count, note}
    DELETE /api/bestiary/collections/<id>/monsters/<entry_id>

    GET    /api/bestiary/environments                   your environments
    POST   /api/bestiary/environments                   {name}
    PATCH  /api/bestiary/environments/<id>              {name}
    DELETE /api/bestiary/environments/<id>
    PUT    /api/bestiary/environments/<id>/monsters/<index>     add a monster
    DELETE /api/bestiary/environments/<id>/monsters/<index>     take it out again

Collections are groups like "Warlock boss dungeon", where each monster has a role (minion, elite,
boss) and a count. Environments are the DM's own answer to "where does this live?", because the
SRD doesn't say. Both store monsters by their rules index, so the stat block always comes from
the SRD data.
"""
from __future__ import annotations

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import select

from . import rules
from .extensions import db
from .models import CollectionEntry, Environment, MonsterCollection, utcnow
from .rules.api import catalogue_page, monster_summary
from .security import json_body, login_required, text

bp = Blueprint("bestiary", __name__, url_prefix="/api/bestiary")

ROLES = {"none": "No role", "minion": "Minion", "elite": "Elite", "boss": "Boss"}
MAX_COLLECTIONS = 100
MAX_ENTRIES = 100
MAX_COUNT = 99
MAX_ENVIRONMENTS = 50
NAME_MAX = 60
ENV_NAME_MAX = 40
NOTES_MAX = 2000
NOTE_MAX = 300


def _invalid(errors: dict[str, str]):
    return jsonify(error="Please fix the highlighted fields.", errors=errors), 400


def _monster(index: str) -> dict:
    monster = rules.get("monsters", index)
    if monster is None:
        abort(404, description=f"There's no monster called '{index}' in the bestiary.")
    return monster


@bp.get("/options")
def options():
    return jsonify(
        roles=[{"value": k, "label": v} for k, v in ROLES.items()],
        max_count=MAX_COUNT, max_entries=MAX_ENTRIES,
        max_collections=MAX_COLLECTIONS, max_environments=MAX_ENVIRONMENTS,
    )


# ---------------------------------------------------------------------------
# Monsters
# ---------------------------------------------------------------------------
@bp.get("/monsters")
@login_required
def monsters():
    extra = []
    if env_id := request.args.get("environment", type=int):
        members = set(_owned_environment(env_id).monsters)
        extra.append(lambda m: m["index"] in members)
    return jsonify(catalogue_page("monsters", extra))


@bp.get("/monsters/<index>")
@login_required
def monster(index: str):
    entry = _monster(index)
    rows = db.session.execute(
        select(CollectionEntry, MonsterCollection)
        .join(MonsterCollection)
        .where(MonsterCollection.user_id == g.user.id, CollectionEntry.monster == index)
        .order_by(MonsterCollection.name)
    ).all()
    return jsonify(
        monster=entry,
        cr=rules.cr_label(entry["challenge_rating"]),
        collections=[{"id": c.id, "name": c.name, "entry_id": e.id, "role": e.role, "count": e.count}
                     for e, c in rows],
        environments=[{"id": env.id, "name": env.name} for env in _environments() if index in env.monsters],
    )


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------
def _owned_collection(collection_id: int) -> MonsterCollection:
    collection = db.session.get(MonsterCollection, collection_id)
    if collection is None or collection.user_id != g.user.id:
        abort(404, description="Collection not found.")
    return collection


def _entry_dict(entry: CollectionEntry) -> dict:
    monster = rules.get("monsters", entry.monster)
    summary = monster_summary(monster) if monster else {"index": entry.monster, "name": entry.monster, "xp": 0}
    return {
        "id": entry.id, "monster": summary, "role": entry.role, "role_label": ROLES.get(entry.role, entry.role),
        "count": entry.count, "note": entry.note, "xp": summary["xp"] * entry.count,
    }


def _collection_summary(c: MonsterCollection) -> dict:
    entries = [_entry_dict(e) for e in c.entries]
    roles = {role: sum(e["count"] for e in entries if e["role"] == role) for role in ROLES}
    return {
        "id": c.id, "name": c.name, "notes": c.notes,
        "monster_count": sum(e["count"] for e in entries),
        "kinds": len(entries),
        "total_xp": sum(e["xp"] for e in entries),
        "roles": roles,
        "created_at": c.created_at.isoformat() + "Z",
        "updated_at": c.updated_at.isoformat() + "Z",
    }


def _collection_detail(c: MonsterCollection) -> dict:
    return {"collection": {**_collection_summary(c), "entries": [_entry_dict(e) for e in c.entries]}}


def _collection_fields(data: dict, current: MonsterCollection | None = None) -> tuple[dict, dict]:
    """Validate name/notes. Returns (values, errors). Only keys that were sent are checked on PATCH."""
    values: dict = {}
    errors: dict[str, str] = {}
    if current is None or "name" in data:
        name = text(data, "name")
        if not name:
            errors["name"] = "Give the collection a name."
        elif len(name) > NAME_MAX:
            errors["name"] = f"Keep the name to {NAME_MAX} characters or fewer."
        else:
            clash = db.session.scalar(select(MonsterCollection).where(
                MonsterCollection.user_id == g.user.id,
                db.func.lower(MonsterCollection.name) == name.lower(),
            ))
            if clash is not None and clash is not current:
                errors["name"] = "You already have a collection with that name."
        values["name"] = name
    if "notes" in data:
        notes = str(data.get("notes") or "").strip()
        if len(notes) > NOTES_MAX:
            errors["notes"] = f"Keep the notes to {NOTES_MAX} characters or fewer."
        values["notes"] = notes
    return values, errors


@bp.get("/collections")
@login_required
def list_collections():
    stmt = (select(MonsterCollection).where(MonsterCollection.user_id == g.user.id)
            .order_by(MonsterCollection.updated_at.desc(), MonsterCollection.id.desc()))
    return jsonify(collections=[_collection_summary(c) for c in db.session.scalars(stmt)],
                   limit=MAX_COLLECTIONS)


@bp.post("/collections")
@login_required
def create_collection():
    data = json_body()
    if len(g.user.monster_collections) >= MAX_COLLECTIONS:
        abort(400, description=f"You can keep up to {MAX_COLLECTIONS} collections. Delete one to make room.")
    values, errors = _collection_fields(data)
    if errors:
        return _invalid(errors)
    collection = MonsterCollection(user_id=g.user.id, **values)
    db.session.add(collection)
    db.session.commit()
    return jsonify(_collection_detail(collection)), 201


@bp.get("/collections/<int:collection_id>")
@login_required
def get_collection(collection_id: int):
    return jsonify(_collection_detail(_owned_collection(collection_id)))


@bp.patch("/collections/<int:collection_id>")
@login_required
def update_collection(collection_id: int):
    collection = _owned_collection(collection_id)
    values, errors = _collection_fields(json_body(), collection)
    if errors:
        return _invalid(errors)
    for key, value in values.items():
        setattr(collection, key, value)
    db.session.commit()
    return jsonify(_collection_detail(collection))


@bp.delete("/collections/<int:collection_id>")
@login_required
def delete_collection(collection_id: int):
    collection = _owned_collection(collection_id)
    db.session.delete(collection)
    db.session.commit()
    return jsonify(message=f"{collection.name} was deleted.")


def _entry_fields(data: dict, partial: bool) -> dict:
    values: dict = {}
    if not partial or "role" in data:
        role = data.get("role", "none")
        if role not in ROLES:
            abort(400, description="Role must be one of: " + ", ".join(ROLES) + ".")
        values["role"] = role
    if not partial or "count" in data:
        count = data.get("count", 1)
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_COUNT:
            abort(400, description=f"Count must be a whole number from 1 to {MAX_COUNT}.")
        values["count"] = count
    if not partial or "note" in data:
        note = str(data.get("note") or "").strip()
        if len(note) > NOTE_MAX:
            abort(400, description=f"Keep the note to {NOTE_MAX} characters or fewer.")
        values["note"] = note
    return values


@bp.post("/collections/<int:collection_id>/monsters")
@login_required
def add_monster(collection_id: int):
    collection = _owned_collection(collection_id)
    data = json_body()
    index = text(data, "monster")
    monster = _monster(index)
    values = _entry_fields(data, partial=False)

    existing = next((e for e in collection.entries if e.monster == index), None)
    if existing is not None:
        # Adding a monster that's already there adds more of it, e.g. two more goblins.
        existing.count = min(existing.count + values["count"], MAX_COUNT)
        if "role" in data:
            existing.role = values["role"]
        if values["note"]:
            existing.note = values["note"]
        message = f"{collection.name} now has {existing.count} × {monster['name']}."
    else:
        if len(collection.entries) >= MAX_ENTRIES:
            abort(400, description=f"A collection holds up to {MAX_ENTRIES} different monsters.")
        collection.entries.append(CollectionEntry(monster=index, **values))
        message = f"{monster['name']} was added to {collection.name}."
    collection.updated_at = utcnow()
    db.session.commit()
    return jsonify(message=message, **_collection_detail(collection)), 201


def _owned_entry(collection: MonsterCollection, entry_id: int) -> CollectionEntry:
    entry = next((e for e in collection.entries if e.id == entry_id), None)
    if entry is None:
        abort(404, description="That monster isn't in this collection.")
    return entry


@bp.patch("/collections/<int:collection_id>/monsters/<int:entry_id>")
@login_required
def update_entry(collection_id: int, entry_id: int):
    collection = _owned_collection(collection_id)
    entry = _owned_entry(collection, entry_id)
    for key, value in _entry_fields(json_body(), partial=True).items():
        setattr(entry, key, value)
    collection.updated_at = utcnow()
    db.session.commit()
    return jsonify(_collection_detail(collection))


@bp.delete("/collections/<int:collection_id>/monsters/<int:entry_id>")
@login_required
def remove_entry(collection_id: int, entry_id: int):
    collection = _owned_collection(collection_id)
    entry = _owned_entry(collection, entry_id)
    name = (rules.get("monsters", entry.monster) or {}).get("name", entry.monster)
    collection.entries.remove(entry)
    collection.updated_at = utcnow()
    db.session.commit()
    return jsonify(message=f"{name} was removed from {collection.name}.", **_collection_detail(collection))


# ---------------------------------------------------------------------------
# Environments
# ---------------------------------------------------------------------------
def _environments() -> list[Environment]:
    stmt = select(Environment).where(Environment.user_id == g.user.id).order_by(db.func.lower(Environment.name))
    return list(db.session.scalars(stmt))


def _owned_environment(env_id: int) -> Environment:
    env = db.session.get(Environment, env_id)
    if env is None or env.user_id != g.user.id:
        abort(404, description="Environment not found.")
    return env


def _environment_dict(env: Environment) -> dict:
    monsters = [rules.get("monsters", i) for i in env.monsters]
    summaries = sorted((monster_summary(m) for m in monsters if m), key=lambda m: (m["challenge_rating"], m["name"]))
    return {"id": env.id, "name": env.name, "monster_count": len(summaries), "monsters": summaries}


def _environment_name(data: dict, current: Environment | None = None) -> tuple[str, str | None]:
    """The new name and an error message, if it's no good."""
    name = text(data, "name")
    error = None
    if not name:
        error = "Give the environment a name."
    elif len(name) > ENV_NAME_MAX:
        error = f"Keep the name to {ENV_NAME_MAX} characters or fewer."
    elif any(e.name.lower() == name.lower() and e is not current for e in _environments()):
        error = "You already have an environment with that name."
    return name, error


@bp.get("/environments")
@login_required
def list_environments():
    return jsonify(environments=[_environment_dict(e) for e in _environments()], limit=MAX_ENVIRONMENTS)


@bp.post("/environments")
@login_required
def create_environment():
    data = json_body()
    if len(g.user.environments) >= MAX_ENVIRONMENTS:
        abort(400, description=f"You can keep up to {MAX_ENVIRONMENTS} environments. Delete one to make room.")
    name, error = _environment_name(data)
    if error:
        return _invalid({"name": error})
    env = Environment(user_id=g.user.id, name=name, monsters=[])
    db.session.add(env)
    db.session.commit()
    return jsonify(environment=_environment_dict(env)), 201


@bp.patch("/environments/<int:env_id>")
@login_required
def rename_environment(env_id: int):
    env = _owned_environment(env_id)
    name, error = _environment_name(json_body(), env)
    if error:
        return _invalid({"name": error})
    env.name = name
    db.session.commit()
    return jsonify(environment=_environment_dict(env))


@bp.delete("/environments/<int:env_id>")
@login_required
def delete_environment(env_id: int):
    env = _owned_environment(env_id)
    db.session.delete(env)
    db.session.commit()
    return jsonify(message=f"{env.name} was deleted. Its monsters are still in the bestiary.")


@bp.put("/environments/<int:env_id>/monsters/<index>")
@login_required
def add_to_environment(env_id: int, index: str):
    env = _owned_environment(env_id)
    monster = _monster(index)
    if index not in env.monsters:
        env.monsters = [*env.monsters, index]  # reassign so SQLAlchemy sees the JSON change
        db.session.commit()
    return jsonify(message=f"{monster['name']} lives in {env.name}.", environment=_environment_dict(env))


@bp.delete("/environments/<int:env_id>/monsters/<index>")
@login_required
def remove_from_environment(env_id: int, index: str):
    env = _owned_environment(env_id)
    monster = _monster(index)
    if index in env.monsters:
        env.monsters = [i for i in env.monsters if i != index]
        db.session.commit()
    return jsonify(message=f"{monster['name']} was taken out of {env.name}.", environment=_environment_dict(env))
