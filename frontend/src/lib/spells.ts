/**
 * Types and helpers for the spell catalogue (backend/tof/spells.py).
 *
 * Spells come straight from the SRD data. The only thing a user stores is which spells they've
 * starred as favourites; which spells a character may learn is decided by the character rules engine.
 */
import type { Option } from "./bestiary";
import { createFavourites } from "./favourites";

export interface SpellSummary {
  index: string;
  name: string;
  level: number;
  school: string;
  classes: string[];
  casting_time: string;
  range: string;
  duration: string;
  components: string[];
  concentration: boolean;
  ritual: boolean;
  favourite?: boolean;
}

export interface SpellResults {
  results: SpellSummary[];
  count: number;
  page: number;
  pages: number;
  per_page: number;
  favourite_count: number;
  facets?: { level: Option[]; school: Option[]; class: Option[] };
}

interface Ref {
  index: string;
  name: string;
}

/** The full SRD spell, as /api/rules/spells/<index> returns it. */
export interface Spell {
  index: string;
  name: string;
  level: number;
  school: Ref;
  casting_time: string;
  range: string;
  components: string[];
  material?: string;
  duration: string;
  concentration: boolean;
  ritual: boolean;
  desc: string[];
  higher_level?: string[];
  classes: Ref[];
  subclasses: Ref[];
  attack_type?: string;
  dc?: { dc_type: Ref; dc_success: string };
  area_of_effect?: { type: string; size: number };
  damage?: {
    damage_type?: Ref;
    damage_at_slot_level?: Record<string, string>;
    damage_at_character_level?: Record<string, string>;
  }[];
  heal_at_slot_level?: Record<string, string>;
}

export interface SpellDetail {
  spell: Spell;
  favourite: boolean;
  characters: { id: number; name: string; sources: string[] }[];
}

export const SPELLS_PATH = "/dm/tomes/spells";
export const spellPath = (index: string) => `${SPELLS_PATH}/${index}`;

const ORDINALS = ["", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th"];

export const levelLabel = (level: number) => (level === 0 ? "Cantrip" : `${ORDINALS[level]} level`);

/** "3rd-level evocation" or "Evocation cantrip" (plus "(ritual)"), the line under a spell's name. */
export function spellLine(s: { level: number; school: string; ritual?: boolean }): string {
  const base = s.level === 0 ? `${s.school} cantrip` : `${ORDINALS[s.level]}-level ${s.school.toLowerCase()}`;
  return s.ritual ? `${base} (ritual)` : base;
}

export function componentsLine(s: Pick<Spell, "components" | "material">): string {
  const parts = s.components.join(", ");
  return s.material ? `${parts} (${s.material.replace(/\.$/, "").replace(/^./, (c) => c.toLowerCase())})` : parts;
}

// ---------------------------------------------------------------- favourites
/** Your favourite spells, and a function to star or unstar one. */
export const useFavouriteSpells = createFavourites("/api/spells");
