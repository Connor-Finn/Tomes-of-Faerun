"""Levelling up in campaigns, and the Dungeon Master's control panel (agreed with Connor, 2026-11-04).

    PUT    /api/campaigns/<id>/rules                    {levelling, hp_methods}  campaign rules (DM)

    GET    /api/campaigns/<id>/instance/level-up        what the next level brings, and the picks it asks for
    POST   /api/campaigns/<id>/instance/level-up/hp-roll  roll the hit die for the next level (once: it's kept)
    POST   /api/campaigns/<id>/instance/level-up        {build?, hp_method}  take the next level
    POST   /api/campaigns/<id>/instance/xp              {gained}  add experience points (XP campaigns)
    POST   /api/campaigns/<id>/instance/spellbook       {spell}   a wizard copies a granted spell into the book

    PUT    /api/campaigns/<id>/instances/<iid>/progress {level?, xp?}       override a player's level or XP (DM)
    POST   /api/campaigns/<id>/instances/<iid>/items    {item, quantity}    hand out an item (DM)
    DELETE /api/campaigns/<id>/instances/<iid>/items/<index>?quantity=n     take items away (DM)
    POST   /api/campaigns/<id>/instances/<iid>/spells   {spell}             grant a spell (DM)
    DELETE /api/campaigns/<id>/instances/<iid>/spells/<index>
    POST   /api/campaigns/<id>/instances/<iid>/notes    {body}              send the player a note (DM)
    DELETE /api/campaigns/<id>/instances/<iid>/notes/<nid>

How levelling works in a campaign:

* The DM picks the campaign's levelling mode. **Manual:** the player presses Level Up whenever the
  table agrees. **XP:** the player adds the experience points they earn; each time the total
  crosses the SRD threshold a level-up is ready.
* A level-up is one level at a time. The app works out everything that changes on its own and only
  asks for the new level's picks (see characters/locks.py for what may change).
* Hit points: the DM ticks which methods players may use (average, roll, maximum). A roll is made
  by the app once and kept until it's used, so it can't be rerolled.
* The DM may override a player's level or XP, hand out and take away items, grant spells and send
  notes, but never changes the player's own picks.
"""
from __future__ import annotations

import copy
import secrets

from flask import Blueprint, abort, g, jsonify, request

from . import campaigns as c
from . import roadmaps
from .characters import engine, locks
from .extensions import db
from .models import CampaignRules, CharacterInstance, InstanceNote, InstanceProgress, utcnow
from .security import json_body, login_required

bp = Blueprint("levelling", __name__, url_prefix="/api/campaigns")

LEVELLING = {"manual": "Manual", "xp": "Experience points"}
DEFAULT_HP_METHODS = ["average", "roll"]
# SRD: the experience points needed for each level (index 0 is level 1)
XP_THRESHOLDS = [0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
                 85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000]
MAX_XP = 10_000_000
MAX_XP_GAIN = 1_000_000
MAX_NOTES = 200
NOTE_MAX = 2000
MAX_GRANTED_SPELLS = 100
# What a character owns rather than how it levelled: kept when its levelling choices are swapped out
# (restoring a backup, the DM setting a level back, following a roadmap).
POSSESSIONS = ("items", "given", "used", "attuned", "granted_spells", "equipped")


# ---------------------------------------------------------------------------
# Rules, progress and notes
# ---------------------------------------------------------------------------
def campaign_rules(campaign) -> dict:
    r = campaign.rules
    levelling = r.levelling if r else "manual"
    methods = list(r.hp_methods) if r else list(DEFAULT_HP_METHODS)
    return {"levelling": levelling, "levelling_label": LEVELLING[levelling],
            "hp_methods": [m for m in engine.HP_METHODS if m in methods]}


def level_for_xp(xp: int) -> int:
    return max(i + 1 for i, t in enumerate(XP_THRESHOLDS) if xp >= t)


def progress(instance: CharacterInstance) -> InstanceProgress:
    if instance.progress is None:
        instance.progress = InstanceProgress(xp=0, granted_spells=[], history={})
    return instance.progress


def level_of(instance: CharacterInstance) -> int:
    return instance.build.get("level", 1)


def levels_owed(instance: CharacterInstance) -> int:
    """Level-ups the character has earned but not taken (XP crossed, or the DM raised the level)."""
    p = instance.progress
    level = level_of(instance)
    target = (p.target_level or 0) if p else 0
    if campaign_rules(instance.campaign)["levelling"] == "xp":
        target = max(target, level_for_xp(p.xp if p else 0))
    return max(0, min(target, engine.MAX_LEVEL) - level)


def can_level_up(instance: CharacterInstance) -> tuple[bool, str | None]:
    level = level_of(instance)
    if level >= engine.MAX_LEVEL:
        return False, f"{instance.name} is level {engine.MAX_LEVEL}, the highest level there is."
    if campaign_rules(instance.campaign)["levelling"] == "xp" and not levels_owed(instance):
        p = instance.progress
        need = XP_THRESHOLDS[level] - (p.xp if p else 0)
        return False, f"{instance.name} needs {need:,} more XP to reach level {level + 1}."
    return True, None


def progress_dict(instance: CharacterInstance) -> dict:
    p = instance.progress
    xp = p.xp if p else 0
    level = level_of(instance)
    allowed, reason = can_level_up(instance)
    granted = list(p.granted_spells) if p else []
    copied = set(instance.build.get("granted_spells") or [])
    return {
        "xp": xp,
        "xp_level": level_for_xp(xp),
        "this_level_xp": XP_THRESHOLDS[level - 1],
        "next_level_xp": XP_THRESHOLDS[level] if level < engine.MAX_LEVEL else None,
        "target_level": p.target_level if p else None,
        "levels_owed": levels_owed(instance),
        "can_level_up": allowed,
        "level_up_blocked": reason,
        "granted_spells": [{"index": i, "name": engine.name_of("spells", i),
                            "level": (engine.rules.get("spells", i) or {}).get("level"),
                            "copied": i in copied} for i in granted],
        "lowest_level": min([int(k) for k in (p.history if p else {})] + [level]),
    }


def notes(instance: CharacterInstance) -> list[dict]:
    if instance.dm_note:
        # The single note from before notes became a list: it becomes the first one.
        instance.notes.append(InstanceNote(body=instance.dm_note, created_at=instance.updated_at))
        instance.dm_note = ""
        db.session.commit()
    return [{"id": n.id, "body": n.body, "sent_at": c._iso(n.created_at)} for n in instance.notes]


def carry_possessions(build: dict, current: dict) -> dict:
    """`build` with what the character owns now (items, DM gifts, granted spells...) instead of its own."""
    out = copy.deepcopy(build)
    for key in POSSESSIONS:
        if key in current:
            out[key] = copy.deepcopy(current[key])
        else:
            out.pop(key, None)
    # A wizard who drops below the level of a copied spell can't keep it in the book for now
    result = engine.check(out)
    bad = {e["field"].split(".", 1)[1] for e in result["errors"] if e["field"].startswith("granted_spells.")}
    if bad:
        out["granted_spells"] = [s for s in out["granted_spells"] if s not in bad]
    return engine.clean(out)


def _problems_response(error: str, problems: list[dict]):
    return jsonify(error=error, errors=problems), 400


# ---------------------------------------------------------------------------
# Campaign rules (DM)
# ---------------------------------------------------------------------------
@bp.put("/<int:campaign_id>/rules")
@login_required
def set_rules(campaign_id: int):
    campaign = c._run(campaign_id)
    data = json_body()
    current = campaign_rules(campaign)
    levelling = data.get("levelling", current["levelling"])
    methods = data.get("hp_methods", current["hp_methods"])
    errors = {}
    if levelling not in LEVELLING:
        errors["levelling"] = "Levelling is Manual or Experience points."
    if not isinstance(methods, list) or not methods or any(m not in engine.HP_METHODS for m in methods):
        errors["hp_methods"] = "Tick at least one way to gain hit points: Average, Roll or Maximum."
    if errors:
        return c._invalid(errors)
    if campaign.rules is None:
        campaign.rules = CampaignRules(levelling=levelling, hp_methods=[])
    campaign.rules.levelling = levelling
    campaign.rules.hp_methods = [m for m in engine.HP_METHODS if m in methods]
    return jsonify(message="Campaign rules saved.", **c._touch(campaign))


# ---------------------------------------------------------------------------
# Level up (player)
# ---------------------------------------------------------------------------
def _start_build(instance: CharacterInstance) -> tuple[dict, dict | None]:
    """The build the next level starts from: the roadmap's plan when following one, or this level's picks."""
    level = level_of(instance) + 1
    f = instance.following
    if f is not None and str(level) in f.roadmap.levels:
        return roadmaps.followed_build(instance.build, f.roadmap.levels, level), {"id": f.roadmap.id, "name": f.roadmap.name}
    return {**copy.deepcopy(instance.build), "level": level}, None


def _changes(before: dict, after: dict) -> list[str]:
    """What the next level brings on its own, in words."""
    out = []
    old, new = before["sheet"], after["sheet"]
    if new["proficiency_bonus"] != old["proficiency_bonus"]:
        out.append(f"Proficiency bonus rises to +{new['proficiency_bonus']}.")
    old_features = {f["index"] for f in old["features"]}
    for f in new["features"]:
        if f["index"] not in old_features and not f.get("chosen") and f["source"] in ("class", "subclass"):
            out.append(f"New feature: {f['name']}.")
    old_slots = (old.get("spellcasting") or {}).get("slots") or {}
    new_slots = (new.get("spellcasting") or {}).get("slots") or {}
    for lvl, n in sorted(new_slots.items(), key=lambda kv: int(kv[0])):
        if n != old_slots.get(lvl, 0):
            out.append(f"Level {lvl} spell slots: {old_slots.get(lvl, 0)} → {n}.")
    old_by_id = {s["id"]: s for s in before["slots"]}
    for s in after["slots"]:
        o = old_by_id.get(s["id"])
        if o and s["choose"] > o["choose"] and s["id"] != "spells:prepared":
            out.append(f"{s['label']}: {o['choose']} → {s['choose']}.")
    return out


def _open_slots(before: dict, after: dict) -> list[str]:
    """The slots a level-up asks about: new ones, ones that grew, and the SRD's allowed swaps."""
    old_by_id = {s["id"]: s for s in before["slots"]}
    out = []
    for s in after["slots"]:
        o = old_by_id.get(s["id"])
        if o is None or s["choose"] > o["choose"] or s["id"] in locks.SWAPPABLE or s["id"] in locks.FREE_CHOICES:
            if not s["id"].startswith(locks.IDENTITY_PREFIXES):
                out.append(s["id"])
    return out


def _hp_info(instance: CharacterInstance, start: dict) -> dict:
    sheet = engine.check(start)["sheet"]
    hit_die = int(sheet["hit_dice"].split("d")[1])
    con = next(a["modifier"] for a in sheet["abilities"] if a["key"] == "con")
    allowed = campaign_rules(instance.campaign)["hp_methods"]
    p = instance.progress
    roll = p.hp_roll["die"] if p and p.hp_roll and p.hp_roll.get("level") == level_of(instance) + 1 else None
    dice = {"average": engine.average_die(hit_die), "max": hit_die, "roll": roll}
    return {"hit_die": hit_die, "con_modifier": con, "rolled": roll,
            "methods": [{"value": m, "label": engine.HP_METHODS[m], "die": dice[m],
                         "gain": None if dice[m] is None else max(1, dice[m] + con)} for m in allowed]}


def _preview(instance: CharacterInstance) -> dict:
    allowed, reason = can_level_up(instance)
    if not allowed:
        return {"allowed": False, "reason": reason, "level": level_of(instance) + 1}
    start, roadmap = _start_build(instance)
    before = engine.check(instance.build)
    after = engine.check(start)
    sub_unlocks = bool(after["subclass_level"] == level_of(instance) + 1 and not instance.build.get("subclass"))
    return {
        "allowed": True, "reason": None, "level": level_of(instance) + 1,
        "build": start, "roadmap": roadmap,
        "subclass_unlocks": sub_unlocks,
        "open_slots": _open_slots(before, after),
        "changes": _changes(before, after),
        "hp": _hp_info(instance, start),
        "swaps": {k: v for k, v in locks.SWAPPABLE.items() if any(s["id"] == k for s in after["slots"])},
    }


@bp.get("/<int:campaign_id>/instance/level-up")
@login_required
def level_up_preview(campaign_id: int):
    instance = c._my_instance(c._as_player(campaign_id))
    return jsonify(level_up=_preview(instance), **c._instance_detail(instance, mine=True))


@bp.post("/<int:campaign_id>/instance/level-up/hp-roll")
@login_required
def roll_hit_points(campaign_id: int):
    campaign = c._as_player(campaign_id)
    instance = c._my_instance(campaign)
    allowed, reason = can_level_up(instance)
    if not allowed:
        abort(400, description=reason)
    if "roll" not in campaign_rules(campaign)["hp_methods"]:
        abort(400, description=f"{campaign.name}'s Dungeon Master doesn't allow rolling for hit points.")
    p = progress(instance)
    level = level_of(instance) + 1
    if not (p.hp_roll and p.hp_roll.get("level") == level):
        hit_die = engine.check(instance.build)["sheet"]["hit_dice"].split("d")[1]
        p.hp_roll = {"level": level, "die": secrets.randbelow(int(hit_die)) + 1}
        db.session.commit()
    return jsonify(level_up=_preview(instance))


def take_level(instance: CharacterInstance, proposed: dict | None, hp_method: str):
    """Level the instance up once. Returns an error response, or (message, stopped_following)."""
    campaign = instance.campaign
    allowed, reason = can_level_up(instance)
    if not allowed:
        abort(400, description=reason)
    start, roadmap = _start_build(instance)
    level = level_of(instance) + 1
    if proposed is None:
        proposed = start
    if not isinstance(proposed, dict) or not isinstance(proposed.get("choices", {}), dict):
        abort(400, description="Send the character's build as an object.")

    # Only the levelling choices come from the request: everything else is the character as it is.
    build = copy.deepcopy(instance.build)
    build["level"] = level
    build["subclass"] = proposed.get("subclass")
    build["choices"] = copy.deepcopy(proposed.get("choices") or {})
    build = engine.clean(build)

    problems = locks.locked_changes(instance.build, build, level_up=True)
    if problems:
        return _problems_response("Earlier picks are locked in a campaign.", problems)

    hp = _hp_info(instance, build)
    method = next((m for m in hp["methods"] if m["value"] == hp_method), None)
    if method is None:
        allowed_labels = " or ".join(m["label"].lower() for m in hp["methods"])
        return c._invalid({"hp_method": f"Choose how to gain hit points: {allowed_labels}."})
    if method["die"] is None:
        return c._invalid({"hp_method": "Roll your hit die first."})
    build["hp_levels"] = {**(build.get("hp_levels") or {}), str(level): {"method": hp_method, "die": method["die"]}}

    result = engine.check(build)
    if not result["valid"]:
        return _problems_response("That level-up breaks the rules.", result["errors"])
    if not result["complete"]:
        return _problems_response(f"Make every choice for level {level} first.", result["missing"])

    p = progress(instance)
    p.history = {**(p.history or {}), str(level - 1): copy.deepcopy(instance.build)}
    p.hp_roll = None
    old_max = engine.check(instance.build)["sheet"]["hit_points"]
    new_max = result["sheet"]["hit_points"]
    if instance.current_hp is not None:
        instance.current_hp = max(0, min(new_max, instance.current_hp + new_max - old_max))
    stopped = None
    if instance.following is not None and (roadmap is None or roadmaps.snapshot(build) != roadmaps.snapshot(start)):
        stopped = instance.following.roadmap.name
        instance.following = None
    if p.target_level and p.target_level <= level:
        p.target_level = None
    instance.build = build
    instance.updated_at = utcnow()
    db.session.commit()
    message = f"{instance.name} is now level {level} in {campaign.name} and gained {method['gain']} hit points."
    if roadmap and not stopped:
        message += f" Following “{roadmap['name']}”."
    if stopped:
        message += f" Choosing by hand stopped following “{stopped}”."
    return message


@bp.post("/<int:campaign_id>/instance/level-up")
@login_required
def level_up(campaign_id: int):
    instance = c._my_instance(c._as_player(campaign_id))
    data = json_body()
    outcome = take_level(instance, data.get("build"), data.get("hp_method"))
    if not isinstance(outcome, str):
        return outcome
    return jsonify(message=outcome, **c._instance_detail(instance, mine=True))


@bp.post("/<int:campaign_id>/instance/xp")
@login_required
def add_xp(campaign_id: int):
    campaign = c._as_player(campaign_id)
    instance = c._my_instance(campaign)
    if campaign_rules(campaign)["levelling"] != "xp":
        abort(400, description=f"{campaign.name} levels up by hand, not by experience points.")
    gained = json_body().get("gained")
    if isinstance(gained, bool) or not isinstance(gained, int) or not 1 <= gained <= MAX_XP_GAIN:
        return c._invalid({"gained": f"Enter the XP you gained: a whole number from 1 to {MAX_XP_GAIN:,}."})
    p = progress(instance)
    before = levels_owed(instance)
    p.xp = min(MAX_XP, p.xp + gained)
    owed = levels_owed(instance)
    db.session.commit()
    message = f"{instance.name} gained {gained:,} XP ({p.xp:,} in all)."
    if owed > before:
        message += f" Level {level_of(instance) + 1} is ready!"
    return jsonify(message=message, **c._instance_detail(instance, mine=True))


@bp.post("/<int:campaign_id>/instance/spellbook")
@login_required
def copy_into_spellbook(campaign_id: int):
    instance = c._my_instance(c._as_player(campaign_id))
    spell = str(json_body().get("spell") or "")
    p = progress(instance)
    if instance.build.get("class") != "wizard":
        abort(400, description="Only wizards copy spells into a spellbook.")
    if spell not in (p.granted_spells or []):
        return c._invalid({"spell": "Copy a spell your Dungeon Master gave you."})
    build = copy.deepcopy(instance.build)
    if spell in (build.get("granted_spells") or []):
        abort(409, description=f"{engine.name_of('spells', spell)} is already in your spellbook.")
    build["granted_spells"] = [*(build.get("granted_spells") or []), spell]
    result = engine.check(build)
    if not result["valid"]:
        return _problems_response("That spell can't go in your spellbook yet.", result["errors"])
    instance.build = build
    instance.updated_at = utcnow()
    db.session.commit()
    return jsonify(message=f"{engine.name_of('spells', spell)} was copied into {instance.name}'s spellbook.",
                   **c._instance_detail(instance, mine=True))


# ---------------------------------------------------------------------------
# The DM's control panel
# ---------------------------------------------------------------------------
def _dm_instance(campaign_id: int, instance_id: int) -> CharacterInstance:
    campaign = c._run(campaign_id)
    return c._players_instance(campaign, instance_id)


def _dm_saved(instance: CharacterInstance, message: str, status: int = 200):
    instance.updated_at = utcnow()
    db.session.commit()
    return jsonify(message=message, **c._instance_detail(instance)), status


def _whole(data: dict, key: str, low: int, high: int, label: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        abort(400, description=f"{label} must be a whole number from {low:,} to {high:,}.")
    return value


@bp.put("/<int:campaign_id>/instances/<int:instance_id>/progress")
@login_required
def override_progress(campaign_id: int, instance_id: int):
    instance = _dm_instance(campaign_id, instance_id)
    data = json_body()
    xp_mode = campaign_rules(instance.campaign)["levelling"] == "xp"
    p = progress(instance)
    said = []
    if "xp" in data:
        p.xp = _whole(data, "xp", 0, MAX_XP, "XP")
        said.append(f"XP set to {p.xp:,}")
    if "level" in data:
        level = _whole(data, "level", 1, engine.MAX_LEVEL, "Level")
        current = level_of(instance)
        if level > current:
            p.target_level = level
            if xp_mode:
                p.xp = max(p.xp, XP_THRESHOLDS[level - 1])
            said.append(f"{instance.name} can level up to level {level}")
        elif level < current:
            snapshot = (p.history or {}).get(str(level))
            if snapshot is None:
                lowest = progress_dict(instance)["lowest_level"]
                return c._invalid({"level": f"{instance.name} can only be set back to a level they've had in this "
                                            f"campaign (level {lowest} or higher)."})
            build = carry_possessions(snapshot, instance.build)
            instance.build = build
            p.history = {k: v for k, v in p.history.items() if int(k) < level}
            p.target_level, p.hp_roll = None, None
            if xp_mode:
                p.xp = min(p.xp, XP_THRESHOLDS[level] - 1) if level < engine.MAX_LEVEL else p.xp
            max_hp = engine.check(build)["sheet"]["hit_points"]
            if instance.current_hp is not None:
                instance.current_hp = min(instance.current_hp, max_hp)
            if instance.following is not None:
                instance.following = None
            said.append(f"{instance.name} is back to level {level}, with the choices they had then")
        else:
            p.target_level = None
    if not said:
        return c._invalid({"level": "Set a level or XP."})
    return _dm_saved(instance, ". ".join(said) + ".")


@bp.post("/<int:campaign_id>/instances/<int:instance_id>/items")
@login_required
def give_item(campaign_id: int, instance_id: int):
    instance = _dm_instance(campaign_id, instance_id)
    data = json_body()
    index = str(data.get("item") or "")
    item = engine.rules.get("equipment", index) or engine.rules.get("magic-items", index)
    if not item:
        return c._invalid({"item": "Choose an item from the catalogue."})
    quantity = _whole(data, "quantity", 1, engine.MAX_ITEM_QUANTITY, "Quantity") if "quantity" in data else 1
    build = copy.deepcopy(instance.build)
    given = dict(build.get("given") or {})
    if index not in given and len(given) >= engine.MAX_EXTRA_ITEMS:
        abort(400, description=f"A character can be given at most {engine.MAX_EXTRA_ITEMS} different items.")
    given[index] = min(engine.MAX_ITEM_QUANTITY, given.get(index, 0) + quantity)
    build["given"] = given
    instance.build = build
    what = f"{quantity} × {item['name']}" if quantity > 1 else item["name"]
    return _dm_saved(instance, f"You gave {what} to {instance.name}.", 201)


@bp.delete("/<int:campaign_id>/instances/<int:instance_id>/items/<index>")
@login_required
def take_item(campaign_id: int, instance_id: int, index: str):
    instance = _dm_instance(campaign_id, instance_id)
    owned = next((i for i in engine.check(instance.build)["sheet"]["inventory"] if i["index"] == index), None)
    if owned is None:
        abort(404, description=f"{instance.name} doesn't have that item.")
    raw = request.args.get("quantity", "1")
    quantity = int(raw) if raw.isdigit() else 0
    if not 1 <= quantity <= owned["quantity"]:
        abort(400, description=f"Take between 1 and {owned['quantity']}.")
    build = copy.deepcopy(instance.build)
    given = dict(build.get("given") or {})
    from_given = min(quantity, given.get(index, 0))
    if from_given:
        given[index] -= from_given
        if not given[index]:
            del given[index]
        build["given"] = given
    rest = quantity - from_given
    if rest:
        used = dict(build.get("used") or {})
        used[index] = used.get(index, 0) + rest
        build["used"] = used
    instance.build = engine.clean(build)
    what = f"{quantity} × {owned['name']}" if quantity > 1 else owned["name"]
    return _dm_saved(instance, f"You took {what} from {instance.name}.")


@bp.post("/<int:campaign_id>/instances/<int:instance_id>/spells")
@login_required
def grant_spell(campaign_id: int, instance_id: int):
    instance = _dm_instance(campaign_id, instance_id)
    index = str(json_body().get("spell") or "")
    spell = engine.rules.get("spells", index)
    if not spell:
        return c._invalid({"spell": "Choose a spell from the catalogue."})
    p = progress(instance)
    if index in (p.granted_spells or []):
        abort(409, description=f"You already gave {instance.name} {spell['name']}.")
    if len(p.granted_spells or []) >= MAX_GRANTED_SPELLS:
        abort(400, description=f"A character can be granted at most {MAX_GRANTED_SPELLS} spells.")
    wizard = instance.build.get("class") == "wizard"
    if wizard and ("wizard" not in engine.spell_classes(spell) or spell["level"] == 0):
        return c._invalid({"spell": f"{spell['name']} isn't a levelled wizard spell, so it can't go in a spellbook."})
    p.granted_spells = [*(p.granted_spells or []), index]
    if not wizard:
        instance.build = {**instance.build, "granted_spells": [*(instance.build.get("granted_spells") or []), index]}
        return _dm_saved(instance, f"{instance.name} now knows {spell['name']}.", 201)
    return _dm_saved(instance, f"You gave {instance.name} {spell['name']}. They can copy it into their spellbook.", 201)


@bp.delete("/<int:campaign_id>/instances/<int:instance_id>/spells/<index>")
@login_required
def revoke_spell(campaign_id: int, instance_id: int, index: str):
    instance = _dm_instance(campaign_id, instance_id)
    p = progress(instance)
    if index not in (p.granted_spells or []):
        abort(404, description="You didn't grant that spell.")
    p.granted_spells = [s for s in p.granted_spells if s != index]
    build = copy.deepcopy(instance.build)
    build["granted_spells"] = [s for s in build.get("granted_spells") or [] if s != index]
    prepared = (build.get("choices") or {}).get("spells:prepared")
    if prepared and index in prepared:
        build["choices"]["spells:prepared"] = [s for s in prepared if s != index]
    instance.build = build
    return _dm_saved(instance, f"You took {engine.name_of('spells', index)} back from {instance.name}.")


@bp.post("/<int:campaign_id>/instances/<int:instance_id>/notes")
@login_required
def send_note(campaign_id: int, instance_id: int):
    instance = _dm_instance(campaign_id, instance_id)
    body = str(json_body().get("body") or "").strip()
    if not body:
        return c._invalid({"body": "Write the note first."})
    if len(body) > NOTE_MAX:
        return c._invalid({"body": f"Keep the note to {NOTE_MAX} characters or fewer."})
    notes(instance)
    if len(instance.notes) >= MAX_NOTES:
        abort(400, description=f"A character can hold up to {MAX_NOTES} notes. Delete an old one first.")
    instance.notes.insert(0, InstanceNote(body=body))
    return _dm_saved(instance, f"Your note was sent to {instance.user.name}.", 201)


@bp.delete("/<int:campaign_id>/instances/<int:instance_id>/notes/<int:note_id>")
@login_required
def delete_note(campaign_id: int, instance_id: int, note_id: int):
    instance = _dm_instance(campaign_id, instance_id)
    note = next((n for n in instance.notes if n.id == note_id), None)
    if note is None:
        abort(404, description="That note isn't on this character.")
    instance.notes.remove(note)
    return _dm_saved(instance, "Note deleted.")
