"""The character rules engine.

A character is stored as a *build*: the player's decisions and nothing else (race, class,
level, ability scores and one list of picks per choice). Everything else on the sheet, such as
hit points, armour class, skill bonuses, features and spell slots, is worked out from the build
and the SRD rules data every time, so the sheet can never drift out of step with the rules.

`analyse(build)` walks the rules in the order a player meets them and returns:

    slots    every choice this build has to make (pick two skills, a fighting style, six
             spells for your spellbook...), with the options and which of them are denied
    errors   picks the rules forbid. A build with errors is never saved.
    missing  choices that are still open. A build with missing choices saves as a draft.

The builder UI renders `slots` directly, so the front end never re-implements a rule: Easy build
hides denied options, Standard build shows them and the API refuses them.

Build shape (all indexes are SRD `index` slugs):

    {
      "name": "Aldric Vane", "level": 1,
      "race": "human", "subrace": null, "class": "fighter", "subclass": null,
      "background": "acolyte", "alignment": "lawful-good",
      "ability_scores": {"method": "standard-array" | "point-buy", "base": {"str": 15, ...}},
      "choices": {"<slot id>": ["<value>", ...]},
      "equipped": {"armor": "chain-mail", "shield": "shield"},
      "notes": {"personality": "...", "ideal": "...", "bond": "...", "flaw": "...", "backstory": "..."}
    }
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from typing import Any

from .. import rules

ABILITIES = ["str", "dex", "con", "int", "wis", "cha"]
ABILITY_NAMES = {
    "str": "Strength", "dex": "Dexterity", "con": "Constitution",
    "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma",
}
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]
POINT_BUY_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
POINT_BUY_BUDGET = 27
ABILITY_METHODS = {"standard-array": "Standard array", "point-buy": "Point buy"}
MAX_LEVEL = 20
MAX_SCORE = 20
BUILD_MODES = ("easy", "standard")
EASY_MAX_CREATION_LEVEL = 3
NOTE_FIELDS = ("personality", "ideal", "bond", "flaw", "backstory")
NOTE_MAX_LENGTH = 2000
NAME_MAX_LENGTH = 60

# Casters who learn a fixed list of spells vs. casters who prepare from their whole class list.
KNOWN_CASTERS = {"bard", "ranger", "sorcerer", "warlock"}
PREPARED_CASTERS = {"cleric", "druid", "paladin", "wizard"}
HALF_CASTERS = {"paladin", "ranger"}
MAGICAL_SECRETS = {"magical-secrets-1", "magical-secrets-2", "magical-secrets-3", "additional-magical-secrets"}
OPTION_KEYS = ("subfeature_options", "expertise_options", "enemy_type_options", "terrain_type_options")


def slug(url: str) -> str:
    """'/api/2014/spells/eldritch-blast' -> 'eldritch-blast'"""
    return url.rstrip("/").rsplit("/", 1)[-1]


def modifier(score: int) -> int:
    return (score - 10) // 2


def signed(n: int) -> str:
    return f"+{n}" if n >= 0 else str(n)


def name_of(kind: str, index: str | None) -> str | None:
    if not index:
        return None
    entry = rules.get(kind, index)
    return entry["name"] if entry else index


def strip_prefix(name: str) -> str:
    """'Skill: Athletics' -> 'Athletics'"""
    return name.split(": ", 1)[1] if name.startswith(("Skill: ", "Saving Throw: ")) else name


# ---------------------------------------------------------------------------
# Rules lookups (cached: the rules data never changes while the app runs)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def class_levels(class_index: str) -> dict[int, dict]:
    return {l["level"]: l for l in rules.load("levels")
            if l.get("class", {}).get("index") == class_index and "subclass" not in l}


@lru_cache(maxsize=None)
def subclass_levels(subclass_index: str) -> dict[int, dict]:
    return {l["level"]: l for l in rules.load("levels") if l.get("subclass", {}).get("index") == subclass_index}


@lru_cache(maxsize=None)
def subclass_level(class_index: str) -> int:
    """The level a class picks its subclass: the first level its (SRD) subclass gains features."""
    cls = rules.get("classes", class_index)
    levels = [lvl for s in cls["subclasses"] for lvl in subclass_levels(s["index"])]
    return min(levels) if levels else 3


@lru_cache(maxsize=None)
def category_items(category_index: str) -> tuple[dict, ...]:
    category = rules.get("equipment-categories", category_index) or {}
    return tuple(e for ref in category.get("equipment", []) if (e := rules.get("equipment", ref["index"])))


@lru_cache(maxsize=None)
def spells_by_level() -> dict[int, tuple[dict, ...]]:
    out: dict[int, list[dict]] = {}
    for s in rules.load("spells"):
        out.setdefault(s["level"], []).append(s)
    return {k: tuple(v) for k, v in out.items()}


def spell_classes(spell: dict) -> set[str]:
    return {c["index"] for c in spell.get("classes", [])}


@lru_cache(maxsize=None)
def proficiency_reference_map() -> dict[str, str]:
    """proficiency index -> the equipment (or category) index it covers, e.g. 'longswords' -> 'longsword'."""
    return {p["index"]: p["reference"]["index"] for p in rules.load("proficiencies") if p.get("reference")}


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------
@dataclass
class Slot:
    id: str
    group: str            # race | class | background | features | abilities | spells | equipment
    label: str
    choose: int
    options: list[dict]   # {"value", "label", "denied"?: reason, ...extra}
    level: int = 1
    kind: str = "pick"    # pick | asi | spell | equipment
    exact: bool = True    # False: pick up to `choose`
    help: str = ""
    selected: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        if self.errors:
            return False
        if self.kind == "asi":
            return len(self.selected) == 2 or (len(self.selected) == 1 and self.selected[0].startswith("feat:"))
        return len(self.selected) == self.choose or (not self.exact and len(self.selected) <= self.choose)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["complete"] = self.complete
        return d


def option(value: str, label: str, denied: str | None = None, **extra) -> dict:
    o = {"value": value, "label": label, **extra}
    if denied:
        o["denied"] = denied
    return o


def flatten_options(option_set: dict) -> tuple[list[dict], int]:
    """A 5e-database choice -> (reference items, how many to pick).

    Nested choices ("one skill and thieves' tools, or two skills") are flattened into one list,
    picking as many as the largest nested choice.
    """
    choose = option_set.get("choose", 1)
    source = option_set["from"]
    if source.get("option_set_type") == "equipment_category":
        return [{"index": e["index"], "name": e["name"]} for e in category_items(source["equipment_category"]["index"])], choose
    if source.get("option_set_type") == "resource_list":
        kind = slug(source["resource_list_url"])
        return [{"index": e["index"], "name": e["name"]} for e in rules.load(kind)], choose
    items: list[dict] = []
    nested_choose = 0
    for o in source.get("options", []):
        if isinstance(o, str):
            items.append({"index": o, "name": o.capitalize()})
        elif o.get("option_type") == "reference":
            items.append(o["item"])
        elif o.get("option_type") == "choice":
            inner, n = flatten_options(o["choice"])
            nested_choose = max(nested_choose, n)
            items.extend(inner)
        elif o.get("option_type") == "string":
            items.append({"index": o["string"], "name": o["string"]})
    if nested_choose:
        choose = max(choose, nested_choose)
    seen: set[str] = set()
    unique = [i for i in items if not (i["index"] in seen or seen.add(i["index"]))]
    return unique, choose


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
@dataclass
class Analysis:
    build: dict
    slots: list[Slot] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)    # {"field", "message"}
    missing: list[dict] = field(default_factory=list)   # {"field", "message"}

    # Resolved state, filled in while walking the rules
    race: dict | None = None
    subrace: dict | None = None
    cls: dict | None = None
    subclass: dict | None = None
    background: dict | None = None
    level: int = 1
    bonuses: dict[str, int] = field(default_factory=lambda: {a: 0 for a in ABILITIES})
    base_scores: dict[str, int] | None = None
    proficiencies: dict[str, str] = field(default_factory=dict)   # index -> source
    expertise: set[str] = field(default_factory=set)
    languages: dict[str, str] = field(default_factory=dict)       # index -> source
    traits: list[str] = field(default_factory=list)
    features: list[tuple[str, int, str]] = field(default_factory=list)  # (index, level, group)
    chosen_features: set[str] = field(default_factory=set)
    feats: list[str] = field(default_factory=list)
    extra_spells: list[tuple[str, str]] = field(default_factory=list)  # (spell index, source)
    inventory: dict[str, int] = field(default_factory=dict)
    stale: list[str] = field(default_factory=list)

    @property
    def choices(self) -> dict[str, list[str]]:
        return self.build.setdefault("choices", {})

    def error(self, where: str, message: str) -> None:
        self.errors.append({"field": where, "message": message})

    def need(self, where: str, message: str) -> None:
        self.missing.append({"field": where, "message": message})

    def scores(self) -> dict[str, int]:
        base = self.base_scores or {a: 10 for a in ABILITIES}
        return {a: base[a] + self.bonuses[a] for a in ABILITIES}

    def add_slot(self, slot: Slot) -> Slot:
        """Register a choice, read the player's picks for it and check them."""
        raw = self.choices.get(slot.id, [])
        picks = [str(v) for v in raw] if isinstance(raw, list) else []
        slot.selected = picks
        by_value = {o["value"]: o for o in slot.options}
        if slot.kind != "asi":
            if len(picks) != len(set(picks)):
                slot.errors.append("You picked the same option twice.")
            for p in picks:
                o = by_value.get(p)
                if o is None:
                    slot.errors.append(f"“{p}” isn't one of the options.")
                elif o.get("denied"):
                    slot.errors.append(f"{o['label']}: {o['denied']}")
            if len(picks) > slot.choose:
                slot.errors.append(f"Pick at most {slot.choose}.")
        for message in slot.errors:
            self.error(slot.id, f"{slot.label}: {message}")
        if not slot.errors and not slot.complete:
            self.need(slot.id, f"{slot.label}: pick {slot.choose - len(picks)} more.")
        self.slots.append(slot)
        return slot

    def valid_picks(self, slot: Slot) -> list[str]:
        """The picks that count: none at all if the slot has errors."""
        return [] if slot.errors else slot.selected


def analyse(build: dict) -> Analysis:
    a = Analysis(build=build)
    _identity(a)
    _race(a)
    _background(a)
    _class(a)
    _ability_scores(a)   # needs racial bonuses; ASIs are added on top in _features
    _features(a)
    _spells(a)
    _invocations(a)
    _equipment(a)
    _prune_stale(a)
    return a


# ----------------------------------------------------------------- identity
def _identity(a: Analysis) -> None:
    b = a.build
    name = str(b.get("name") or "").strip()
    if not name:
        a.need("name", "Give your character a name.")
    elif len(name) > NAME_MAX_LENGTH:
        a.error("name", f"Names can be at most {NAME_MAX_LENGTH} characters.")

    level = b.get("level", 1)
    if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= MAX_LEVEL:
        a.error("level", f"Level must be a whole number from 1 to {MAX_LEVEL}.")
        level = 1
    a.level = level

    if b.get("classes") or b.get("multiclass"):
        a.error("class", "Multiclassing isn't available yet. A character has one class.")

    alignment = b.get("alignment")
    if alignment and not rules.get("alignments", alignment):
        a.error("alignment", "Choose an alignment from the list.")
    elif not alignment:
        a.need("alignment", "Choose an alignment.")

    notes = b.get("notes") or {}
    if not isinstance(notes, dict):
        a.error("notes", "Notes must be an object.")
    else:
        for key, value in notes.items():
            if key not in NOTE_FIELDS:
                a.error(f"notes.{key}", f"Unknown note “{key}”.")
            elif not isinstance(value, str) or len(value) > NOTE_MAX_LENGTH:
                a.error(f"notes.{key}", f"Notes must be text of at most {NOTE_MAX_LENGTH} characters.")


# --------------------------------------------------------------------- race
def _race(a: Analysis) -> None:
    b = a.build
    if not b.get("race"):
        a.need("race", "Choose a race.")
        return
    race = rules.get("races", b["race"])
    if not race:
        a.error("race", f"“{b['race']}” isn't a race in the rules.")
        return
    a.race = race

    subraces = [s["index"] for s in race.get("subraces", [])]
    sub = b.get("subrace")
    if sub and sub not in subraces:
        a.error("subrace", f"{race['name']} has no subrace “{sub}”.")
    elif subraces and not sub:
        a.need("subrace", f"Choose a {race['name'].lower()} subrace.")
    elif sub:
        a.subrace = rules.get("subraces", sub)

    for bonus in race.get("ability_bonuses", []) + (a.subrace or {}).get("ability_bonuses", []):
        a.bonuses[bonus["ability_score"]["index"]] += bonus["bonus"]
    for lang in race.get("languages", []):
        a.languages[lang["index"]] = race["name"]

    if opts := race.get("ability_bonus_options"):
        options = [option(o["ability_score"]["index"], f"{ABILITY_NAMES[o['ability_score']['index']]} +{o['bonus']}")
                   for o in opts["from"]["options"]]
        slot = a.add_slot(Slot("race:ability-bonus", "race", "Ability score increases", opts["choose"], options,
                               help=f"{race['name']}s choose {opts['choose']} different ability scores to raise by 1."))
        for ability in a.valid_picks(slot):
            a.bonuses[ability] += 1

    if opts := race.get("language_options"):
        _language_slot(a, "race:languages", "race", f"{race['name']} language", opts)

    trait_indexes = [t["index"] for t in race.get("traits", [])]
    trait_indexes += [t["index"] for t in (a.subrace or {}).get("racial_traits", [])]
    for index in trait_indexes:
        _trait(a, index)


def _trait(a: Analysis, index: str) -> None:
    trait = rules.get("traits", index)
    if not trait:
        return
    a.traits.append(index)
    for p in trait.get("proficiencies", []):
        a.proficiencies.setdefault(p["index"], trait["name"])
    if opts := trait.get("proficiency_choices"):
        _proficiency_slot(a, f"trait:{index}", "race", trait["name"], opts, help=" ".join(trait.get("desc", [])))
    if opts := trait.get("language_options"):
        _language_slot(a, f"trait:{index}", "race", trait["name"], opts)
    specific = trait.get("trait_specific") or {}
    if opts := specific.get("spell_options"):
        items, choose = flatten_options(opts)
        slot = a.add_slot(Slot(f"trait:{index}", "race", trait["name"], choose,
                               [option(i["index"], i["name"]) for i in items], kind="spell",
                               help=" ".join(trait.get("desc", []))))
        a.extra_spells += [(s, trait["name"]) for s in a.valid_picks(slot)]
    if opts := specific.get("subtrait_options"):
        items, choose = flatten_options(opts)
        slot = a.add_slot(Slot(f"trait:{index}", "race", trait["name"], choose,
                               [option(i["index"], i["name"]) for i in items], help=" ".join(trait.get("desc", []))))
        for sub in a.valid_picks(slot):
            a.traits.append(sub)


def _language_slot(a: Analysis, slot_id: str, group: str, label: str, opts: dict) -> None:
    items, choose = flatten_options(opts)
    taken = dict(a.languages)
    options = [option(i["index"], i["name"], f"You already speak it ({taken[i['index']]})." if i["index"] in taken else None)
               for i in items]
    slot = a.add_slot(Slot(slot_id, group, label, choose, options,
                           help=f"Pick {choose} language{'s' if choose > 1 else ''} you can speak, read and write."))
    for lang in a.valid_picks(slot):
        a.languages[lang] = label


def _proficiency_slot(a: Analysis, slot_id: str, group: str, label: str, opts: dict, help: str = "",
                      level: int = 1) -> Slot:
    items, choose = flatten_options(opts)
    options = []
    for i in items:
        source = a.proficiencies.get(i["index"])
        options.append(option(i["index"], strip_prefix(i["name"]),
                              f"You're already proficient ({source})." if source else None))
    slot = a.add_slot(Slot(slot_id, group, label, choose, options, help=help or opts.get("desc", ""), level=level))
    for p in a.valid_picks(slot):
        a.proficiencies[p] = label
    return slot


# --------------------------------------------------------------- background
def _background(a: Analysis) -> None:
    b = a.build
    if not b.get("background"):
        a.need("background", "Choose a background.")
        return
    bg = rules.get("backgrounds", b["background"])
    if not bg:
        a.error("background", f"“{b['background']}” isn't a background in the rules.")
        return
    a.background = bg
    for p in bg.get("starting_proficiencies", []):
        a.proficiencies.setdefault(p["index"], bg["name"])
    if opts := bg.get("language_options"):
        _language_slot(a, "background:languages", "background", f"{bg['name']} languages", opts)


# -------------------------------------------------------------------- class
def _class(a: Analysis) -> None:
    b = a.build
    if not b.get("class"):
        a.need("class", "Choose a class.")
        return
    cls = rules.get("classes", b["class"])
    if not cls:
        a.error("class", f"“{b['class']}” isn't a class in the rules.")
        return
    a.cls = cls
    for p in cls.get("proficiencies", []):
        a.proficiencies.setdefault(p["index"], cls["name"])
    for i, opts in enumerate(cls.get("proficiency_choices", [])):
        label = f"{cls['name']} skills" if i == 0 else f"{cls['name']} proficiencies"
        _proficiency_slot(a, f"class:proficiency-{i}", "class", label, opts)

    sub = b.get("subclass")
    unlock = subclass_level(cls["index"])
    allowed = {s["index"] for s in cls["subclasses"]}
    if sub and sub not in allowed:
        a.error("subclass", f"{cls['name']} has no subclass “{sub}”.")
    elif sub and a.level < unlock:
        a.stale.append("subclass")   # picked before lowering the level: dropped on save
    elif sub:
        a.subclass = rules.get("subclasses", sub)
    elif a.level >= unlock:
        a.need("subclass", f"Choose a subclass. {cls['name']}s pick one at level {unlock}.")


# ----------------------------------------------------------- ability scores
def _ability_scores(a: Analysis) -> None:
    data = a.build.get("ability_scores") or {}
    method = data.get("method")
    base = data.get("base")
    if not method or not base:
        a.need("ability_scores", "Assign your ability scores.")
        return
    if method not in ABILITY_METHODS:
        a.error("ability_scores", "Use the standard array or point buy.")
        return
    if not isinstance(base, dict) or set(base) != set(ABILITIES) or \
            not all(isinstance(v, int) and not isinstance(v, bool) for v in base.values()):
        a.error("ability_scores", "Give a whole-number score for each of the six abilities.")
        return
    if method == "standard-array" and sorted(base.values(), reverse=True) != STANDARD_ARRAY:
        a.error("ability_scores", "The standard array is 15, 14, 13, 12, 10 and 8, each used once.")
        return
    if method == "point-buy":
        if any(v not in POINT_BUY_COST for v in base.values()):
            a.error("ability_scores", "With point buy each score starts between 8 and 15.")
            return
        spent = sum(POINT_BUY_COST[v] for v in base.values())
        if spent > POINT_BUY_BUDGET:
            a.error("ability_scores", f"That costs {spent} points; point buy gives you {POINT_BUY_BUDGET}.")
            return
    a.base_scores = dict(base)


# ----------------------------------------------------------------- features
def _features(a: Analysis) -> None:
    if not a.cls:
        return
    levels = class_levels(a.cls["index"])
    sub_levels = subclass_levels(a.subclass["index"]) if a.subclass else {}
    for lvl in range(1, a.level + 1):
        for group, entry in (("class", levels.get(lvl)), ("subclass", sub_levels.get(lvl))):
            for ref in (entry or {}).get("features", []):
                _feature(a, ref["index"], lvl, group)


def _feature(a: Analysis, index: str, lvl: int, group: str) -> None:
    feature = rules.get("features", index)
    if not feature:
        return
    a.features.append((index, lvl, group))
    if "ability-score-improvement" in index:
        _asi(a, index, lvl)
        return
    specific = feature.get("feature_specific") or {}
    for key in OPTION_KEYS:
        if opts := specific.get(key):
            if key == "expertise_options":
                _expertise(a, index, feature, opts, lvl)
            else:
                items, choose = flatten_options(opts)
                taken = a.chosen_features | {t for t in _picked_strings(a)}
                options = [option(i["index"], _feature_label(i["name"]),
                                  "You already have this." if i["index"] in taken else None) for i in items]
                slot = a.add_slot(Slot(f"feature:{index}", "features", feature["name"], choose, options,
                                       level=lvl, help=" ".join(feature.get("desc", [])[:2])))
                for pick in a.valid_picks(slot):
                    a.chosen_features.add(pick)


def _picked_strings(a: Analysis) -> set[str]:
    """Favoured enemies and terrains picked so far (they can't repeat)."""
    return {v for s in a.slots if s.id.startswith("feature:") for v in s.selected}


def _feature_label(name: str) -> str:
    """'Fighting Style: Dueling' -> 'Dueling', 'Metamagic: Careful Spell' -> 'Careful Spell'."""
    return name.split(": ", 1)[1] if ": " in name else name


def _expertise(a: Analysis, index: str, feature: dict, opts: dict, lvl: int) -> None:
    items, choose = flatten_options(opts)
    options = []
    for i in items:
        denied = None
        if i["index"] not in a.proficiencies:
            denied = "You need to be proficient first."
        elif i["index"] in a.expertise:
            denied = "You already have expertise in this."
        options.append(option(i["index"], strip_prefix(i["name"]), denied))
    slot = a.add_slot(Slot(f"feature:{index}", "features", feature["name"], choose, options, level=lvl,
                           help="Choose proficiencies to double your proficiency bonus for."))
    a.expertise.update(a.valid_picks(slot))


def _asi(a: Analysis, index: str, lvl: int) -> None:
    scores = a.scores()
    options = [option(ab, f"{ABILITY_NAMES[ab]} +1",
                      f"{ABILITY_NAMES[ab]} is already {MAX_SCORE}." if scores[ab] >= MAX_SCORE else None, kind="ability")
               for ab in ABILITIES]
    for feat in rules.load("feats"):
        denied = None
        for pre in feat.get("prerequisites", []):
            ab, minimum = pre["ability_score"]["index"], pre["minimum_score"]
            if scores[ab] < minimum:
                denied = f"Needs {ABILITY_NAMES[ab]} {minimum}."
        if feat["index"] in a.feats:
            denied = "You already have this feat."
        options.append(option(f"feat:{feat['index']}", f"Feat: {feat['name']}", denied, kind="feat"))
    slot = Slot(f"asi:{index}", "features", f"Ability Score Improvement (level {lvl})", 2, options, level=lvl,
                kind="asi", help="Raise one ability score by 2, or two scores by 1 each, to a maximum of 20. "
                                 "Or take a feat instead.")
    picks = [str(v) for v in a.choices.get(slot.id, [])] if isinstance(a.choices.get(slot.id), list) else []
    by_value = {o["value"]: o for o in options}
    feats = [p for p in picks if p.startswith("feat:")]
    if any(p not in by_value for p in picks):
        slot.errors.append("Pick ability scores or a feat from the list.")
    elif feats and len(picks) != 1:
        slot.errors.append("A feat replaces the whole improvement: pick only the feat.")
    elif len(picks) > 2:
        slot.errors.append("Pick two increases (they can be the same ability) or one feat.")
    else:
        running = dict(scores)
        for p in picks:
            o = by_value[p]
            if o["value"].startswith("feat:"):
                if o.get("denied"):
                    slot.errors.append(f"{o['label']}: {o['denied']}")
            else:
                running[p] += 1
                if running[p] > MAX_SCORE:
                    slot.errors.append(f"{ABILITY_NAMES[p]} can't go above {MAX_SCORE}.")
    a.add_slot(slot)
    if not slot.errors:
        for p in picks:
            if p.startswith("feat:"):
                a.feats.append(p[5:])
            else:
                a.bonuses[p] += 1


# ------------------------------------------------------------------- spells
@dataclass
class Casting:
    ability: str
    max_spell_level: int
    slots: dict[int, int]
    cantrips_known: int
    spells_known: int | None


def casting_info(a: Analysis) -> Casting | None:
    if not a.cls or not a.cls.get("spellcasting"):
        return None
    level = class_levels(a.cls["index"]).get(a.level) or {}
    sc = level.get("spellcasting") or {}
    slots = {n: sc.get(f"spell_slots_level_{n}", 0) for n in range(1, 10) if sc.get(f"spell_slots_level_{n}", 0)}
    if not slots and not sc.get("cantrips_known"):
        return None   # paladins and rangers start casting at level 2
    return Casting(
        ability=a.cls["spellcasting"]["spellcasting_ability"]["index"],
        max_spell_level=max(slots) if slots else 0,
        slots=slots,
        cantrips_known=sc.get("cantrips_known", 0),
        spells_known=sc.get("spells_known"),
    )


def _spell_option(s: dict, class_index: str, max_level: int, any_class: bool = False) -> dict:
    denied = None
    if not any_class and class_index not in spell_classes(s):
        denied = "It isn't on your class's spell list."
    elif s["level"] > max_level:
        denied = f"You can't cast level {s['level']} spells yet."
    return option(s["index"], s["name"], denied, level=s["level"], school=s["school"]["name"])


def _spells(a: Analysis) -> None:
    casting = casting_info(a)
    if not casting:
        return
    cls = a.cls["index"]
    name = a.cls["name"]
    leveled = [s for lvl in range(1, 10) for s in spells_by_level().get(lvl, ())]

    if casting.cantrips_known:
        a.add_slot(Slot("spells:cantrips", "spells", "Cantrips", casting.cantrips_known,
                        [_spell_option(s, cls, 0) for s in spells_by_level().get(0, ())], kind="spell",
                        help=f"Cantrips are spells you can cast at will. {name}s know {casting.cantrips_known}."))

    if cls in KNOWN_CASTERS and casting.spells_known:
        a.add_slot(Slot("spells:known", "spells", "Spells known", casting.spells_known,
                        [_spell_option(s, cls, casting.max_spell_level) for s in leveled], kind="spell",
                        help=f"{name}s learn a fixed list of spells. At level {a.level} you know {casting.spells_known}, "
                             f"up to level {casting.max_spell_level}."))
    if cls == "wizard":
        size = 6 + 2 * (a.level - 1)
        book = a.add_slot(Slot("spells:spellbook", "spells", "Spellbook", size,
                               [_spell_option(s, cls, casting.max_spell_level) for s in leveled], kind="spell",
                               help=f"Your spellbook starts with six level 1 wizard spells and gains two each level: "
                                    f"{size} at level {a.level}."))
        in_book = set(a.valid_picks(book))
        prep = _prepared_count(a, casting)
        a.add_slot(Slot("spells:prepared", "spells", "Prepared spells", prep,
                        [option(s["index"], s["name"], None if s["index"] in in_book else "It isn't in your spellbook.",
                                level=s["level"], school=s["school"]["name"]) for s in leveled
                         if s["index"] in in_book or cls in spell_classes(s)],
                        kind="spell", exact=False,
                        help=f"Each day you prepare up to {prep} spells from your spellbook."))
    elif cls in PREPARED_CASTERS:
        prep = _prepared_count(a, casting)
        a.add_slot(Slot("spells:prepared", "spells", "Prepared spells", prep,
                        [_spell_option(s, cls, casting.max_spell_level) for s in leveled], kind="spell", exact=False,
                        help=f"{name}s prepare spells from the whole {name.lower()} list each day: up to {prep} "
                             f"at the moment."))

    secrets = 2 * sum(1 for f, _, _ in a.features if f in MAGICAL_SECRETS)
    if secrets:
        a.add_slot(Slot("spells:magical-secrets", "spells", "Magical Secrets", secrets,
                        [_spell_option(s, cls, casting.max_spell_level, any_class=True) for s in leveled
                         if not s["index"] in set(a.choices.get("spells:known", []))],
                        kind="spell", help="Spells from any class's list. They count as bard spells for you."))

    level_entry = class_levels(cls).get(a.level) or {}
    for n in range(6, 10):
        if (level_entry.get("class_specific") or {}).get(f"mystic_arcanum_level_{n}"):
            a.add_slot(Slot(f"spells:arcanum-{n}", "spells", f"Mystic Arcanum (level {n})", 1,
                            [_spell_option(s, cls, n) for s in spells_by_level().get(n, ())], kind="spell",
                            help=f"One level {n} warlock spell you can cast once per long rest without a slot."))

    if a.subclass:
        for entry in a.subclass.get("spells", []):
            if all(_prereq_met(a, p) for p in entry.get("prerequisites", [])):
                a.extra_spells.append((entry["spell"]["index"], a.subclass["name"]))


def _prepared_count(a: Analysis, casting: Casting) -> int:
    score = a.scores()[casting.ability]
    lvl = a.level // 2 if a.cls["index"] in HALF_CASTERS else a.level
    return max(1, modifier(score) + lvl)


def _prereq_met(a: Analysis, prereq: dict) -> bool:
    if prereq["type"] == "level":
        match = re.search(r"(\d+)$", prereq.get("index", "")) if "index" in prereq else None
        lvl = int(match.group(1)) if match else prereq.get("level", 1)
        return a.level >= lvl
    if prereq["type"] == "feature":
        index = prereq.get("index") or slug(prereq["feature"])
        return index in a.chosen_features or any(f == index for f, _, _ in a.features)
    if prereq["type"] == "spell":
        return slug(prereq["spell"]) in set(a.choices.get("spells:cantrips", [])) | set(a.choices.get("spells:known", []))
    return True


def _invocations(a: Analysis) -> None:
    if not a.cls or not any(f == "eldritch-invocations" for f, _, _ in a.features):
        return
    count = (class_levels(a.cls["index"]).get(a.level, {}).get("class_specific") or {}).get("invocations_known", 0)
    feature = rules.get("features", "eldritch-invocations")
    options = []
    for ref in feature["feature_specific"]["invocations"]:
        inv = rules.get("features", ref["index"])
        reasons = []
        for pre in inv.get("prerequisites", []):
            if not _prereq_met(a, pre):
                if pre["type"] == "level":
                    reasons.append(f"Needs warlock level {pre['level']}.")
                elif pre["type"] == "spell":
                    reasons.append(f"Needs the {name_of('spells', slug(pre['spell']))} cantrip.")
                else:
                    reasons.append(f"Needs {name_of('features', slug(pre['feature']))}.")
        options.append(option(inv["index"], _feature_label(inv["name"]), " ".join(reasons) or None))
    slot = a.add_slot(Slot("feature:eldritch-invocations", "features", "Eldritch Invocations", count, options,
                           level=2, help=f"At level {a.level} you know {count} invocations."))
    a.chosen_features.update(a.valid_picks(slot))


# ---------------------------------------------------------------- equipment
def _equipment(a: Analysis) -> None:
    sources = []
    if a.cls:
        for e in a.cls.get("starting_equipment", []):
            a.inventory[e["equipment"]["index"]] = a.inventory.get(e["equipment"]["index"], 0) + e["quantity"]
        sources += [(f"class-{i}", a.cls["name"], o) for i, o in enumerate(a.cls.get("starting_equipment_options", []))]
    if a.background:
        for e in a.background.get("starting_equipment", []):
            a.inventory[e["equipment"]["index"]] = a.inventory.get(e["equipment"]["index"], 0) + e["quantity"]
        sources += [(f"background-{i}", a.background["name"], o)
                    for i, o in enumerate(a.background.get("starting_equipment_options", []))]
    for key, owner, opts in sources:
        _equipment_slot(a, f"equipment:{key}", owner, opts)
    _equipped(a)


def _bundle(o: dict) -> tuple[list[tuple[str, int]], list[dict], str]:
    """One option of an equipment choice -> (fixed items, nested choices, label)."""
    t = o.get("option_type")
    if t == "counted_reference":
        name = o["of"]["name"]
        return [(o["of"]["index"], o["count"])], [], f"{o['count']} × {name}" if o["count"] > 1 else name
    if t == "choice":
        desc = o["choice"].get("desc") or "an item of your choice"
        return [], [o["choice"]], desc[:1].upper() + desc[1:]
    if t == "multiple":
        items, choices, labels = [], [], []
        for part in o["items"]:
            i, c, label = _bundle(part)
            items += i
            choices += c
            labels.append(label)
        return items, choices, " and ".join(labels)
    return [], [], "?"


def _equipment_slot(a: Analysis, slot_id: str, owner: str, opts: dict) -> None:
    label = (opts.get("desc") or "Equipment").strip()
    label = label[:1].upper() + label[1:]
    if opts["from"].get("option_set_type") == "equipment_category":
        items, choose = flatten_options(opts)
        slot = a.add_slot(Slot(slot_id, "equipment", f"{owner}: {label}", choose,
                               [option(i["index"], i["name"]) for i in items], kind="equipment"))
        for pick in a.valid_picks(slot):
            a.inventory[pick] = a.inventory.get(pick, 0) + 1
        return

    bundles = [_bundle(o) for o in opts["from"]["options"]]
    letters = "abcdefgh"
    slot = a.add_slot(Slot(slot_id, "equipment", f"{owner}: {label}", 1,
                           [option(letters[i], f"({letters[i]}) {b[2]}") for i, b in enumerate(bundles)],
                           kind="equipment"))
    for pick in a.valid_picks(slot):
        items, choices, _ = bundles[letters.index(pick)]
        for index, count in items:
            a.inventory[index] = a.inventory.get(index, 0) + count
        for k, choice in enumerate(choices):
            sub_items, sub_choose = flatten_options(choice)
            desc = choice.get("desc") or "an item"
            sub = a.add_slot(Slot(f"{slot_id}:{pick}{k}", "equipment", f"{owner}: {desc}", sub_choose,
                                  [option(i["index"], i["name"]) for i in sub_items], kind="equipment"))
            # "Two martial weapons" may be the same weapon twice, so quantities add up
            for p in a.valid_picks(sub):
                a.inventory[p] = a.inventory.get(p, 0) + 1


def _equipped(a: Analysis) -> None:
    equipped = a.build.get("equipped")
    if equipped is None:
        return
    if not isinstance(equipped, dict):
        a.error("equipped", "Equipped items must be an object.")
        return
    for slot_name, want in (("armor", ("Light", "Medium", "Heavy")), ("shield", ("Shield",))):
        index = equipped.get(slot_name)
        if not index:
            continue
        item = rules.get("equipment", index)
        if not item or item.get("armor_category") not in want:
            a.error(f"equipped.{slot_name}", f"“{index}” can't be worn as {'armour' if slot_name == 'armor' else 'a shield'}.")
        elif index not in a.inventory:
            a.stale.append(f"equipped.{slot_name}")


def _prune_stale(a: Analysis) -> None:
    """Remember choices that no longer apply (e.g. picks for a class you switched away from)."""
    live = {s.id for s in a.slots}
    a.stale += [f"choices.{k}" for k in a.choices if k not in live]


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------
def clean(build: dict) -> dict:
    """A copy of the build with stale choices removed and unknown keys dropped."""
    keep = ("name", "level", "race", "subrace", "class", "subclass", "background", "alignment",
            "ability_scores", "choices", "equipped", "notes")
    out = {k: build.get(k) for k in keep if k in build}
    out["name"] = str(out.get("name") or "").strip()
    out.setdefault("level", 1)
    out["choices"] = dict(build.get("choices") or {})
    a = analyse(out)
    for path in a.stale:
        if path.startswith("choices."):
            out["choices"].pop(path[len("choices."):], None)
        elif path.startswith("equipped."):
            out["equipped"] = {**out["equipped"], path[len("equipped."):]: None}
        else:
            out[path] = None
    if "equipped" not in build:
        out["equipped"] = default_equipped(analyse(out).inventory)
    return out


def default_equipped(inventory: dict[str, int]) -> dict:
    """Wear the best armour and a shield, if the character owns them."""
    armors = [rules.get("equipment", i) for i in inventory]
    body = [x for x in armors if x and x.get("armor_category") in ("Light", "Medium", "Heavy")]
    body.sort(key=lambda x: x["armor_class"]["base"], reverse=True)
    shield = next((x for x in armors if x and x.get("armor_category") == "Shield"), None)
    return {"armor": body[0]["index"] if body else None, "shield": shield["index"] if shield else None}


# ---------------------------------------------------------------------------
# The character sheet
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def skills() -> tuple[dict, ...]:
    return tuple({"index": s["index"], "name": s["name"], "ability": s["ability_score"]["index"]}
                 for s in rules.load("skills"))


def sheet(a: Analysis) -> dict:
    """Everything the character sheet shows, worked out from the build."""
    b = a.build
    scores = a.scores()
    mods = {k: modifier(v) for k, v in scores.items()}
    prof = (class_levels(a.cls["index"]).get(a.level, {}).get("prof_bonus", 2) if a.cls else 2)
    profs = set(a.proficiencies)
    feature_ids = {f for f, _, _ in a.features} | a.chosen_features

    abilities = []
    for ab in ABILITIES:
        save_prof = f"saving-throw-{ab}" in profs
        abilities.append({
            "key": ab, "name": ABILITY_NAMES[ab],
            "base": (a.base_scores or {}).get(ab), "bonus": a.bonuses[ab], "score": scores[ab], "modifier": mods[ab],
            "save": mods[ab] + (prof if save_prof else 0), "save_proficient": save_prof,
        })

    skill_rows = []
    for s in skills():
        key = f"skill-{s['index']}"
        proficient = key in profs
        expert = key in a.expertise
        bonus = mods[s["ability"]] + (prof * (2 if expert else 1) if proficient else 0)
        skill_rows.append({**s, "proficient": proficient, "expertise": expert, "bonus": bonus})
    perception = next(s["bonus"] for s in skill_rows if s["index"] == "perception")

    hit_die = a.cls["hit_die"] if a.cls else 8
    hp = hit_die + mods["con"] + sum(max(1, hit_die // 2 + 1 + mods["con"]) for _ in range(a.level - 1))
    hp_notes = []
    if "dwarven-toughness" in a.traits:
        hp += a.level
        hp_notes.append("Dwarven Toughness")
    if "draconic-resilience" in feature_ids:
        hp += a.level
        hp_notes.append("Draconic Resilience")

    inventory = _inventory(a)
    equipped = b.get("equipped") or {}
    armor = rules.get("equipment", equipped["armor"]) if equipped.get("armor") and equipped["armor"] in a.inventory else None
    shield = rules.get("equipment", equipped["shield"]) if equipped.get("shield") and equipped["shield"] in a.inventory else None
    ac, ac_note = _armor_class(mods, armor, shield, feature_ids)

    speed = (a.race or {}).get("speed", 30)
    if a.cls and a.cls["index"] == "monk" and not armor and not shield:
        speed += (class_levels("monk").get(a.level, {}).get("class_specific") or {}).get("unarmored_movement", 0)
    if "fast-movement" in feature_ids and not (armor and armor.get("armor_category") == "Heavy"):
        speed += 10

    return {
        "summary": {
            "name": b.get("name") or "Unnamed adventurer", "level": a.level,
            "race": name_of("races", b.get("race")), "subrace": name_of("subraces", b.get("subrace")),
            "class": name_of("classes", b.get("class")), "subclass": a.subclass["name"] if a.subclass else None,
            "background": name_of("backgrounds", b.get("background")),
            "alignment": name_of("alignments", b.get("alignment")),
        },
        "abilities": abilities,
        "ability_method": ABILITY_METHODS.get((b.get("ability_scores") or {}).get("method")),
        "proficiency_bonus": prof,
        "hit_points": hp,
        "hit_points_note": ", ".join(hp_notes) or None,
        "hit_dice": f"{a.level}d{hit_die}",
        "armor_class": ac,
        "armor_class_note": ac_note,
        "initiative": mods["dex"],
        "speed": speed,
        "passive_perception": 10 + perception,
        "saving_throws": [x["key"] for x in abilities if x["save_proficient"]],
        "skills": skill_rows,
        "languages": sorted(name_of("languages", l) for l in a.languages),
        "proficiencies": _proficiency_groups(a),
        "features": _feature_list(a),
        "spellcasting": _spell_sheet(a, mods, prof),
        "inventory": inventory,
        "gold": ((a.background or {}).get("starting_gold") or {}).get("quantity", 0),
        "attacks": _attacks(a, mods, prof, feature_ids),
        "equipped": {"armor": armor["index"] if armor else None, "shield": shield["index"] if shield else None},
        "notes": {k: (b.get("notes") or {}).get(k, "") for k in NOTE_FIELDS},
    }


def _armor_class(mods: dict, armor: dict | None, shield: dict | None, features: set[str]) -> tuple[int, str]:
    if armor:
        ac_data = armor["armor_class"]
        dex = mods["dex"] if ac_data.get("dex_bonus") else 0
        if ac_data.get("max_bonus") is not None:
            dex = min(dex, ac_data["max_bonus"])
        ac, note = ac_data["base"] + dex, armor["name"]
    elif "draconic-resilience" in features:
        ac, note = 13 + mods["dex"], "Draconic Resilience"
    elif "barbarian-unarmored-defense" in features:
        ac, note = 10 + mods["dex"] + mods["con"], "Unarmored Defense"
    elif "monk-unarmored-defense" in features and not shield:
        ac, note = 10 + mods["dex"] + mods["wis"], "Unarmored Defense"
    else:
        ac, note = 10 + mods["dex"], "Unarmoured"
    if shield:
        ac += shield["armor_class"]["base"]
        note += " and shield"
    if armor and any(f.endswith("fighting-style-defense") for f in features):
        ac += 1
        note += ", Defense fighting style"
    return ac, note


def _inventory(a: Analysis) -> list[dict]:
    equipped = set((a.build.get("equipped") or {}).values())
    out = []
    for index, qty in a.inventory.items():
        item = rules.get("equipment", index)
        if not item:
            continue
        out.append({
            "index": index, "name": item["name"], "quantity": qty,
            "category": item["equipment_category"]["name"], "weight": item.get("weight"),
            "equipped": index in equipped,
            "contents": [{"name": c["item"]["name"], "quantity": c["quantity"]} for c in item.get("contents", [])],
        })
    out.sort(key=lambda i: (not i["equipped"], i["category"], i["name"]))
    return out


def _proficiency_groups(a: Analysis) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {"armor": [], "weapons": [], "tools": []}
    for index in a.proficiencies:
        p = rules.get("proficiencies", index)
        if not p or p["type"] in ("Skills", "Saving Throws"):
            continue
        key = {"Armor": "armor", "Weapons": "weapons"}.get(p["type"], "tools")
        groups[key].append(p["name"])
    return {k: sorted(v) for k, v in groups.items()}


def _feature_list(a: Analysis) -> list[dict]:
    out = []
    for index in a.traits:
        t = rules.get("traits", index)
        if t:
            out.append({"index": index, "name": t["name"], "source": "race", "level": 1, "desc": t.get("desc", [])})
    if a.background and a.background.get("feature"):
        f = a.background["feature"]
        out.append({"index": f"background-{a.background['index']}", "name": f["name"], "source": "background",
                    "level": 1, "desc": f.get("desc", [])})
    for index, lvl, group in a.features:
        f = rules.get("features", index)
        if "ability-score-improvement" in index:
            continue
        out.append({"index": index, "name": f["name"], "source": group, "level": lvl, "desc": f.get("desc", [])})
    for index in sorted(a.chosen_features):
        f = rules.get("features", index)
        if f:
            out.append({"index": index, "name": f["name"], "source": "subclass" if f.get("subclass") else "class",
                        "level": f.get("level", 1), "desc": f.get("desc", []), "chosen": True})
    for slot in a.slots:
        if slot.kind == "asi" and not slot.errors:
            for p in slot.selected:
                if p.startswith("feat:") and (feat := rules.get("feats", p[5:])):
                    out.append({"index": feat["index"], "name": feat["name"], "source": "feat", "level": slot.level,
                                "desc": feat.get("desc", [])})
    return out


def _spell_sheet(a: Analysis, mods: dict, prof: int) -> dict | None:
    casting = casting_info(a)
    if not casting and not a.extra_spells:
        return None
    picked: dict[str, dict] = {}

    def add(index: str, source: str, prepared: bool = True) -> None:
        s = rules.get("spells", index)
        if s and index not in picked:
            picked[index] = {"index": index, "name": s["name"], "level": s["level"], "school": s["school"]["name"],
                             "source": source, "prepared": prepared}

    valid = {s.id: a.valid_picks(s) for s in a.slots if s.group == "spells"}
    prepared = set(valid.get("spells:prepared", []))
    for key, label in (("spells:cantrips", "Cantrip"), ("spells:known", "Known"), ("spells:magical-secrets", "Magical Secrets")):
        for i in valid.get(key, []):
            add(i, label)
    for key in valid:
        if key.startswith("spells:arcanum-"):
            for i in valid[key]:
                add(i, "Mystic Arcanum")
    for i in valid.get("spells:spellbook", []):
        add(i, "Spellbook", prepared=i in prepared)
    if a.cls and a.cls["index"] in PREPARED_CASTERS - {"wizard"}:
        for i in prepared:
            add(i, "Prepared")
    for index, source in a.extra_spells:
        add(index, source)
    ability = casting.ability if casting else "int"
    return {
        "ability": ability,
        "ability_name": ABILITY_NAMES[ability],
        "save_dc": 8 + prof + mods[ability],
        "attack_bonus": prof + mods[ability],
        "slots": {str(k): v for k, v in (casting.slots if casting else {}).items()},
        "max_spell_level": casting.max_spell_level if casting else 0,
        "spells": sorted(picked.values(), key=lambda s: (s["level"], s["name"])),
    }


def _attacks(a: Analysis, mods: dict, prof: int, features: set[str]) -> list[dict]:
    refs = proficiency_reference_map()
    covered = {refs.get(p, p) for p in a.proficiencies}
    archery = any(f.endswith("fighting-style-archery") for f in features)
    dueling = any(f.endswith("fighting-style-dueling") for f in features)
    out = []
    for index in a.inventory:
        w = rules.get("equipment", index)
        if not w or not w.get("damage"):
            continue
        props = {p["index"] for p in w.get("properties", [])}
        ranged = w.get("weapon_range") == "Ranged"
        if "finesse" in props:
            ability = "dex" if mods["dex"] >= mods["str"] else "str"
        else:
            ability = "dex" if ranged else "str"
        category = "simple-weapons" if w.get("weapon_category") == "Simple" else "martial-weapons"
        proficient = index in covered or category in covered
        bonus = mods[ability] + (prof if proficient else 0) + (2 if archery and ranged else 0)
        dmg_mod = mods[ability] + (2 if dueling and not ranged and "two-handed" not in props else 0)
        dice = w["damage"]["damage_dice"]
        out.append({
            "index": index, "name": w["name"], "attack_bonus": bonus, "proficient": proficient,
            "damage": f"{dice}{'' if dmg_mod == 0 else (' + ' if dmg_mod > 0 else ' − ') + str(abs(dmg_mod))}",
            "damage_type": w["damage"]["damage_type"]["name"],
            "range": f"{w['range']['normal']}/{w['range']['long']} ft" if w.get("range", {}).get("long") else
                     f"{w.get('range', {}).get('normal', 5)} ft",
            "properties": [p["name"] for p in w.get("properties", [])],
        })
    return out


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def check(build: dict, *, build_mode: str = "standard", previous_level: int = 0) -> dict:
    """Analyse a build for the builder: slots, errors and what's still missing."""
    a = analyse(build)
    if build_mode == "easy" and a.level > EASY_MAX_CREATION_LEVEL and a.level > previous_level:
        a.error("level", f"Easy build creates characters up to level {EASY_MAX_CREATION_LEVEL}. "
                         f"Level them further with a roadmap, or switch to Standard build.")
    return {
        "valid": not a.errors,
        "complete": not a.errors and not a.missing,
        "errors": a.errors,
        "missing": a.missing,
        "slots": [s.to_dict() for s in a.slots],
        "subclass_level": subclass_level(a.cls["index"]) if a.cls else None,
        "sheet": sheet(a),
    }
