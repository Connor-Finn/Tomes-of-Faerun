/**
 * Types and helpers for the spell catalogue (backend/tof/spells.py).
 *
 * Spells come straight from the SRD data. The only thing a user stores is which spells they've
 * starred as favourites; which spells a character may learn is decided by the character rules engine.
 */
import { useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";
import type { Option } from "./bestiary";

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
// One shared list for the whole app, so a star clicked in the builder shows in the catalogue too.
// It's kept per user, so logging in as someone else never shows the last person's stars.
let favourites: Set<string> | null = null;
let owner: number | null = null;
let loading: Promise<void> | null = null;
const listeners = new Set<() => void>();

function publish(next: Set<string>) {
  favourites = next;
  listeners.forEach((l) => l());
}

function loadFavourites(userId: number): Promise<void> {
  if (owner !== userId) {
    favourites = null;
    owner = userId;
    loading = null;
  }
  loading ??= api.get<{ favourites: SpellSummary[] }>("/api/spells/favourites").then((res) => {
    if (res.ok) publish(new Set(res.data.favourites.map((s) => s.index)));
    loading = null;
  });
  return loading;
}

/** Your favourite spells, and a function to star or unstar one. */
export function useFavouriteSpells() {
  const { user } = useAuth();
  const userId = user?.id ?? null;
  const [, rerender] = useState(0);
  useEffect(() => {
    const listener = () => rerender((n) => n + 1);
    listeners.add(listener);
    if (userId !== null && (!favourites || owner !== userId)) void loadFavourites(userId);
    return () => {
      listeners.delete(listener);
    };
  }, [userId]);

  async function toggle(index: string): Promise<{ ok: boolean; message?: string; error?: string }> {
    const current = favourites ?? new Set<string>();
    const on = !current.has(index);
    const next = new Set(current);
    if (on) next.add(index);
    else next.delete(index);
    publish(next); // star straight away; put it back if the server says no
    const url = `/api/spells/favourites/${encodeURIComponent(index)}`;
    const res = on ? await api.put<{ message: string }>(url) : await api.delete<{ message: string }>(url);
    if (!res.ok) {
      publish(current);
      return { ok: false, error: res.data.error ?? "Couldn't change your favourites." };
    }
    return { ok: true, message: res.data.message };
  }

  const mine = owner === userId ? favourites : null;
  return { favourites: mine, isFavourite: (index: string) => Boolean(mine?.has(index)), toggle };
}
