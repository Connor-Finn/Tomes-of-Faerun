import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

/**
 * Types and hooks for the Character Manager.
 *
 * The server owns the rules (backend/tof/characters/engine.py): the front end sends a build,
 * and gets back the sheet, every open choice ("slots") and anything the rules refuse.
 */
export type BuildMode = "easy" | "standard";
export type Ability = "str" | "dex" | "con" | "int" | "wis" | "cha";
export type NoteField = "personality" | "ideal" | "bond" | "flaw" | "backstory";

export interface Build {
  name?: string;
  level?: number;
  race?: string | null;
  subrace?: string | null;
  class?: string | null;
  subclass?: string | null;
  background?: string | null;
  alignment?: string | null;
  ability_scores?: {
    method?: string;
    base?: Partial<Record<Ability, number>>;
    /** Rolled scores only: the six rolls the app made, and which roll they were. */
    rolls?: number[];
    roll_id?: number;
  } | null;
  choices?: Record<string, string[]>;
  equipped?: { armor?: string | null; shield?: string | null } | null;
  /** Items added from the catalogue on top of the starting kit: index -> quantity. */
  items?: Record<string, number>;
  /** Magic items the character is attuned to. */
  attuned?: string[];
  notes?: Partial<Record<NoteField, string>>;
  /** Campaign characters only (the campaign API manages these): */
  hp_levels?: Record<string, { method: HpMethod; die: number }>;
  given?: Record<string, number>;
  used?: Record<string, number>;
  granted_spells?: string[];
}

export type HpMethod = "average" | "roll" | "max";

export interface AbilityRoll {
  id: number;
  rolls: number[];
  dice: number[][];
}

export interface CharacterSummary {
  id: number;
  name: string;
  level: number;
  race: string | null;
  subrace: string | null;
  class: string | null;
  class_index: string | null;
  subclass: string | null;
  background: string | null;
  build_mode: BuildMode;
  status: "complete" | "draft";
  template: string | null;
  created_at: string;
  updated_at: string;
}

export interface SlotOption {
  value: string;
  label: string;
  denied?: string;
  level?: number;
  school?: string;
  kind?: "ability" | "feat";
}

export interface Slot {
  id: string;
  group: "race" | "class" | "background" | "features" | "abilities" | "spells" | "equipment";
  label: string;
  choose: number;
  options: SlotOption[];
  level: number;
  kind: "pick" | "asi" | "spell" | "equipment";
  exact: boolean;
  help: string;
  selected: string[];
  errors: string[];
  complete: boolean;
}

export interface Problem {
  field: string;
  message: string;
}

export interface AbilityRow {
  key: Ability;
  name: string;
  base: number | null;
  bonus: number;
  score: number;
  modifier: number;
  save: number;
  save_proficient: boolean;
}

export interface Sheet {
  summary: {
    name: string;
    level: number;
    race: string | null;
    subrace: string | null;
    class: string | null;
    subclass: string | null;
    background: string | null;
    alignment: string | null;
  };
  abilities: AbilityRow[];
  ability_method: string | null;
  proficiency_bonus: number;
  hit_points: number;
  hit_points_note: string | null;
  hit_dice: string;
  hit_point_levels: { level: number; method: HpMethod; die: number; gain: number }[];
  armor_class: number;
  armor_class_note: string;
  initiative: number;
  speed: number;
  /** Rule-bending gear: allowed, but flagged with the SRD's penalty. */
  warnings: { code: string; message: string }[];
  attuned: string[];
  max_attuned: number;
  used_items: { index: string; name: string; quantity: number }[];
  passive_perception: number;
  saving_throws: Ability[];
  skills: { index: string; name: string; ability: Ability; proficient: boolean; expertise: boolean; bonus: number }[];
  languages: string[];
  proficiencies: { armor: string[]; weapons: string[]; tools: string[] };
  features: { index: string; name: string; source: string; level: number; desc: string[]; chosen?: boolean }[];
  spellcasting: null | {
    ability: Ability;
    ability_name: string;
    save_dc: number;
    attack_bonus: number;
    slots: Record<string, number>;
    max_spell_level: number;
    spells: { index: string; name: string; level: number; school: string; source: string; prepared: boolean }[];
  };
  inventory: {
    index: string;
    name: string;
    quantity: number;
    kind: "equipment" | "magic";
    category: string;
    weight: number | null;
    equipped: boolean;
    /** How many of these the player added from the catalogue (the rest came with the starting kit). */
    added: number;
    /** How many the DM handed out in a campaign, and how many were used up or dropped. */
    given: number;
    used: number;
    rarity: string | null;
    attunement: boolean | null;
    attuned: boolean;
    contents: { name: string; quantity: number }[];
  }[];
  gold: number;
  attacks: {
    index: string;
    name: string;
    attack_bonus: number;
    proficient: boolean;
    damage: string;
    damage_type: string;
    range: string;
    properties: string[];
  }[];
  equipped: { armor: string | null; shield: string | null };
  notes: Record<NoteField, string>;
}

export interface CheckResult {
  valid: boolean;
  complete: boolean;
  errors: Problem[];
  missing: Problem[];
  slots: Slot[];
  subclass_level: number | null;
  sheet: Sheet;
}

export interface CharacterDetail extends CheckResult {
  character: CharacterSummary & { build: Build };
}

export interface Template {
  id: string;
  name: string;
  summary: string;
  level: number;
  race: string;
  class: string;
  background: string;
  build_mode: BuildMode;
  hit_points: number;
  armor_class: number;
}

export interface CharacterOptions {
  races: {
    index: string;
    name: string;
    speed: number;
    size: string;
    ability_bonuses: { ability: Ability; bonus: number }[];
    subraces: { index: string; name: string; desc: string }[];
    traits: string[];
    summary: string;
    age: string;
  }[];
  classes: {
    index: string;
    name: string;
    hit_die: number;
    saving_throws: Ability[];
    spellcaster: boolean;
    spellcasting_ability: Ability | null;
    subclass_level: number;
    subclasses: { index: string; name: string; desc: string }[];
  }[];
  backgrounds: { index: string; name: string; skills: string[]; feature: string | null }[];
  alignments: { index: string; name: string; desc: string }[];
  abilities: { key: Ability; name: string }[];
  ability_methods: { value: string; label: string }[];
  hp_methods: { value: HpMethod; label: string }[];
  standard_array: number[];
  point_buy: { budget: number; costs: Record<string, number> };
  build_modes: BuildMode[];
  easy_max_level: number;
  max_level: number;
  note_fields: NoteField[];
}

export const BUILD_MODE_LABELS: Record<BuildMode, string> = { easy: "Easy build", standard: "Standard build" };

export const NOTE_LABELS: Record<NoteField, string> = {
  personality: "Personality traits",
  ideal: "Ideals",
  bond: "Bonds",
  flaw: "Flaws",
  backstory: "Backstory",
};

export const characterPath = (id: number, page = "sheet") => `/play/characters/c/${id}/${page}`;

export const signed = (n: number) => (n >= 0 ? `+${n}` : `−${Math.abs(n)}`);

/** "Level 3 Hill Dwarf Cleric (Life)" */
export function describe(c: Pick<CharacterSummary, "level" | "race" | "subrace" | "class" | "subclass">): string {
  const race = c.subrace ?? c.race;
  const cls = c.class ? `${c.class}${c.subclass ? ` (${c.subclass})` : ""}` : null;
  return [`Level ${c.level}`, race, cls].filter(Boolean).join(" ");
}

let optionsCache: CharacterOptions | null = null;

/** Races, classes, backgrounds... loaded once. */
export function useCharacterOptions(): CharacterOptions | null {
  const [options, setOptions] = useState<CharacterOptions | null>(optionsCache);
  useEffect(() => {
    if (optionsCache) return;
    void api.get<CharacterOptions>("/api/characters/options").then((res) => {
      if (res.ok) {
        optionsCache = res.data;
        setOptions(res.data);
      }
    });
  }, []);
  return options;
}

/** Load one character; `reload` refetches and `replace` swaps in a fresh copy from a PATCH. */
export function useCharacter(id: number) {
  const [detail, setDetail] = useState<CharacterDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "missing" | "error">("loading");

  const reload = useCallback(async () => {
    const res = await api.get<CharacterDetail>(`/api/characters/${id}`);
    if (res.ok) {
      setDetail(res.data);
      setStatus("ready");
    } else {
      setStatus(res.status === 404 ? "missing" : "error");
    }
  }, [id]);

  useEffect(() => {
    setStatus("loading");
    void reload();
  }, [reload]);

  return { detail, status, reload, replace: setDetail };
}
