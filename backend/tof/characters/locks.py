"""What a campaign character may change, and when (agreed with Connor, 2026-11-04).

Once a character is in a campaign its earlier picks are locked: race, class, background, ability
scores and every choice made at an earlier level stay as they are. The only changes allowed are:

    any time        name, notes, alignment, what's worn, attunement, prepared spells, items used up
                    or dropped, and copying a spell the DM granted into a wizard's spellbook
    at a level-up   the new level's picks (a subclass when it unlocks, an ability score improvement
                    or feat, new spells, invocations, fighting styles...), plus the swaps the SRD
                    allows: one known spell and one eldritch invocation

Items and hit points are not the player's to change here: the DM hands items out, and the
campaign API records hit points at each level-up.
"""
from __future__ import annotations

from collections import Counter

from .engine import name_of, pick_name

# Never change once in a campaign (the campaign API manages items, granted items and hit points)
FIXED = {
    "race": "race", "subrace": "subrace", "class": "class", "background": "background",
    "ability_scores": "ability scores", "items": "starting items", "given": "items from the DM",
    "hp_levels": "hit points per level",
}
# Picks that can change at any time
FREE_CHOICES = {"spells:prepared"}
# Picks where a level-up may swap one old pick for a new one (SRD: known spells and invocations)
SWAPPABLE = {"spells:known": "known spell", "feature:eldritch-invocations": "eldritch invocation"}
# Picks that belong to who the character is: never change, not even at a level-up
IDENTITY_PREFIXES = ("equipment:", "race:", "trait:", "background:")


def _problem(field: str, message: str) -> dict:
    return {"field": field, "message": message}


def locked_changes(old: dict, new: dict, *, level_up: bool, copyable: set[str] | frozenset = frozenset()) -> list[dict]:
    """Every change from `old` to `new` the campaign rules don't allow. Empty means it's fine.

    `level_up`: the new build is the next level's (one level up, with that level's new picks).
    `copyable`: spells the DM granted that a wizard may copy into the spellbook.
    """
    problems: list[dict] = []
    for key, label in FIXED.items():
        if (old.get(key) or None) != (new.get(key) or None):
            problems.append(_problem(key, f"Your {label} can't change in a campaign."))

    old_level, new_level = old.get("level", 1), new.get("level", 1)
    if new_level != old_level + (1 if level_up else 0):
        problems.append(_problem("level", "Level up one level at a time, through Level Up."
                                 if level_up or new_level > old_level else "Your level can't go down in a campaign."))

    if old.get("subclass") != new.get("subclass") and not (level_up and not old.get("subclass")):
        problems.append(_problem("subclass", "Your subclass is locked once chosen."))

    old_granted, new_granted = set(old.get("granted_spells") or []), set(new.get("granted_spells") or [])
    if old_granted - new_granted:
        problems.append(_problem("granted_spells", "Spells copied into your spellbook stay there."))
    for index in sorted(new_granted - old_granted - set(copyable)):
        problems.append(_problem(f"granted_spells.{index}",
                                 f"{name_of('spells', index)}: only spells your DM gave you can be copied in."))

    old_choices, new_choices = old.get("choices") or {}, new.get("choices") or {}
    for slot_id in sorted(set(old_choices) | set(new_choices)):
        if slot_id in FREE_CHOICES:
            continue
        before, after = Counter(old_choices.get(slot_id) or []), Counter(new_choices.get(slot_id) or [])
        if before == after:
            continue
        removed, added = before - after, after - before
        if slot_id.startswith(IDENTITY_PREFIXES):
            problems.append(_problem(slot_id, "Picks from your race, background and starting equipment are locked."))
        elif not level_up:
            problems.append(_problem(slot_id, "Earlier picks are locked in a campaign. New picks come with Level Up."))
        elif slot_id in SWAPPABLE and sum(removed.values()) <= 1:
            continue
        elif removed:
            names = ", ".join(pick_name(v) for v in removed)
            extra = f" You may swap one {SWAPPABLE[slot_id]} per level." if slot_id in SWAPPABLE else ""
            problems.append(_problem(slot_id, f"{names}: earlier picks are locked in a campaign.{extra}"))
        elif not added:
            continue
    return problems
