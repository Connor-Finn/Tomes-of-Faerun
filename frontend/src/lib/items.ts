/**
 * Types and helpers for the items catalogue (backend/tof/items.py): SRD equipment and magic
 * items in one tome. A user stores which items they've starred; characters store the items
 * they've added on top of their starting kit (build.items).
 */
import type { Option } from "./bestiary";
import { createFavourites } from "./favourites";

export type ItemKind = "equipment" | "magic";

export interface ItemSummary {
  index: string;
  name: string;
  kind: ItemKind;
  category: string;
  category_index: string;
  type: string;
  cost: string | null;
  weight: number | null;
  rarity: string | null;
  attunement: string | null;
  favourite?: boolean;
}

export interface ItemResults {
  results: ItemSummary[];
  count: number;
  page: number;
  pages: number;
  per_page: number;
  favourite_count: number;
  facets?: { kind: Option[]; category: Option[]; rarity: Option[] };
}

interface Ref {
  index: string;
  name: string;
}

interface Dice {
  damage_dice: string;
  damage_type: Ref;
}

/** An SRD equipment entry or magic item, as /api/rules/<kind>/<index> returns it. */
export interface Item {
  index: string;
  name: string;
  equipment_category: Ref;
  desc?: string[];
  // equipment
  cost?: { quantity: number; unit: string };
  weight?: number;
  weapon_category?: string;
  category_range?: string;
  damage?: Dice;
  two_handed_damage?: Dice;
  range?: { normal: number; long?: number };
  throw_range?: { normal: number; long?: number };
  properties?: Ref[];
  special?: string[];
  armor_category?: string;
  armor_class?: { base: number; dex_bonus: boolean; max_bonus?: number };
  str_minimum?: number;
  stealth_disadvantage?: boolean;
  contents?: { item: Ref; quantity: number }[];
  quantity?: number;
  speed?: { quantity: number; unit: string };
  capacity?: string;
  // magic items
  rarity?: { name: string };
  variants?: Ref[];
  image?: string;
}

export interface ItemDetail {
  item: Item;
  kind: ItemKind;
  summary: ItemSummary;
  favourite: boolean;
  characters: { id: number; name: string; quantity: number; added: boolean }[];
}

export const ITEMS_PATH = "/dm/tomes/items";
export const itemPath = (index: string) => `${ITEMS_PATH}/${index}`;
export const rulesUrl = (kind: ItemKind, index: string) =>
  `/api/rules/${kind === "magic" ? "magic-items" : "equipment"}/${encodeURIComponent(index)}`;

/** Your favourite items, and a function to star or unstar one. */
export const useFavouriteItems = createFavourites("/api/items");
