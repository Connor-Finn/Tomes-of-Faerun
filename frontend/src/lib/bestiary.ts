/**
 * Types and helpers for the Bestiary (backend/tof/bestiary.py).
 *
 * Monsters come straight from the SRD data. A DM's own collections and environments only store
 * each monster's `index` plus their choices (role, count, notes).
 */
export type Role = "none" | "minion" | "elite" | "boss";

export const ROLES: { value: Role; label: string }[] = [
  { value: "boss", label: "Boss" },
  { value: "elite", label: "Elite" },
  { value: "minion", label: "Minion" },
  { value: "none", label: "No role" },
];
export const ROLE_LABELS: Record<Role, string> = { none: "No role", minion: "Minion", elite: "Elite", boss: "Boss" };
export const MAX_COUNT = 99;

export interface MonsterSummary {
  index: string;
  name: string;
  size: string;
  type: string;
  alignment: string;
  challenge_rating: number;
  cr: string;
  xp: number;
  hit_points: number;
  armor_class: number | null;
  image: string | null;
}

export interface Option {
  value: string;
  label: string;
}

export interface MonsterPage {
  results: MonsterSummary[];
  count: number;
  page: number;
  pages: number;
  per_page: number;
  facets?: { type: Option[]; size: Option[]; cr: Option[] };
}

interface Named {
  name: string;
  desc: string;
  usage?: { type: string; times?: number; dice?: string; min_value?: number; rest_types?: string[] };
}

/** The full SRD stat block, as /api/rules/monsters/<index> returns it. */
export interface Monster {
  index: string;
  name: string;
  size: string;
  type: string;
  subtype?: string;
  alignment: string;
  armor_class: { type: string; value: number; armor?: { name: string }[]; desc?: string }[];
  hit_points: number;
  hit_dice: string;
  hit_points_roll: string;
  speed: Record<string, string | boolean>;
  strength: number;
  dexterity: number;
  constitution: number;
  intelligence: number;
  wisdom: number;
  charisma: number;
  proficiencies: { value: number; proficiency: { index: string; name: string } }[];
  damage_vulnerabilities: string[];
  damage_resistances: string[];
  damage_immunities: string[];
  condition_immunities: { name: string }[];
  senses: Record<string, string | number>;
  languages: string;
  challenge_rating: number;
  proficiency_bonus: number;
  xp: number;
  desc?: string;
  image?: string;
  special_abilities?: Named[];
  actions?: Named[];
  reactions?: Named[];
  legendary_actions?: Named[];
}

export interface SavedIn {
  collections: { id: number; name: string; entry_id: number; role: Role; count: number }[];
  environments: { id: number; name: string }[];
}

export interface MonsterDetail extends SavedIn {
  monster: Monster;
  cr: string;
}

export interface CollectionSummary {
  id: number;
  name: string;
  notes: string;
  monster_count: number;
  kinds: number;
  total_xp: number;
  roles: Record<Role, number>;
  created_at: string;
  updated_at: string;
}

export interface CollectionEntry {
  id: number;
  monster: MonsterSummary;
  role: Role;
  role_label: string;
  count: number;
  note: string;
  xp: number;
}

export interface Collection extends CollectionSummary {
  entries: CollectionEntry[];
}

export interface Environment {
  id: number;
  name: string;
  monster_count: number;
  monsters: MonsterSummary[];
}

export const BESTIARY_PATH = "/dm/tomes/bestiary";
export const COLLECTIONS_PATH = "/dm/tomes/collections";
export const ENVIRONMENTS_PATH = "/dm/tomes/environments";
export const monsterPath = (index: string) => `${BESTIARY_PATH}/${index}`;
export const collectionPath = (id: number) => `${COLLECTIONS_PATH}/${id}`;

export const modifier = (score: number) => Math.floor((score - 10) / 2);
export const signed = (n: number) => (n >= 0 ? `+${n}` : `${n}`);
export const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export const xp = (n: number) => `${n.toLocaleString("en-GB")} XP`;

/** "Huge dragon, chaotic evil" */
export function creatureLine(m: { size: string; type: string; subtype?: string; alignment: string }): string {
  const kind = m.subtype ? `${m.type} (${m.subtype})` : m.type;
  return `${m.size} ${kind}${m.alignment ? `, ${m.alignment}` : ""}`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}
