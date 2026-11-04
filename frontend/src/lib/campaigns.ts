/**
 * Types and paths for campaigns and parties (backend/tof/campaigns.py and parties.py).
 *
 * A campaign is run by a Dungeon Master and played by the party attached to it. Each player brings
 * one character, which becomes an *instance*: its own copy that levels up and takes damage in that
 * campaign while the base character in the Character Manager stays untouched.
 */
import type { BuildMode, CharacterSummary, CheckResult, Build } from "./characters";
import type { CollectionSummary } from "./bestiary";
import type { RoadmapSummary } from "./roadmaps";

export type CampaignStatus = "planning" | "active" | "finished";

export const STATUSES: { value: CampaignStatus; label: string }[] = [
  { value: "planning", label: "Planning" },
  { value: "active", label: "Active" },
  { value: "finished", label: "Finished" },
];

export interface Person {
  id: number;
  name: string;
  avatar_url: string | null;
}

export interface InstanceSummary {
  id: number;
  name: string;
  player: Person;
  character_id: number | null;
  level: number;
  race: string | null;
  class: string | null;
  subclass: string | null;
  build_mode: BuildMode;
  max_hp: number;
  current_hp: number;
  temp_hp: number;
  dm_note: string;
  updated_at: string;
}

/** What other players see of someone's character: just enough to know who's at the table. */
export interface InstanceGlimpse {
  id: number;
  name: string;
  level: number;
  class: string | null;
}

export interface CampaignSummary {
  id: number;
  name: string;
  description: string;
  status: CampaignStatus;
  status_label: string;
  dm: Person;
  party: { id: number; name: string } | null;
  player_count: number;
  session_count: number;
  last_played: string | null;
  created_at: string;
  updated_at: string;
  my_instance?: InstanceSummary | null;
}

export interface SessionEntry {
  id: number;
  played_on: string;
  title: string;
  summary: string;
}

export interface Encounter {
  id: number;
  attached_at: string;
  collection: CollectionSummary;
}

export interface Campaign extends CampaignSummary {
  role: "dm" | "player";
  players: (Person & { instance: InstanceSummary | InstanceGlimpse | null })[];
  sessions: SessionEntry[];
  my_instance: InstanceSummary | null;
  /** DM only */
  dm_notes?: string;
  encounters?: Encounter[];
}

export interface InstanceBackup {
  name: string;
  level: number;
  race: string | null;
  class: string | null;
  subclass: string | null;
  build_mode: BuildMode;
  max_hp: number;
  current_hp: number;
  temp_hp: number;
  reason: string;
  saved_at: string;
}

export interface InstanceFollowing {
  roadmap_id: number;
  name: string;
  start_level: number;
  end_level: number;
  /** The next level the roadmap has planned, or null when it ends here. */
  next_level: number | null;
  followed_at: string;
}

export interface InstanceDetail extends CheckResult {
  instance: InstanceSummary & {
    build: Build;
    campaign: { id: number; name: string };
    base_character: CharacterSummary | null;
    /** Only on your own character: */
    following?: InstanceFollowing | null;
    backup?: InstanceBackup | null;
    roadmaps?: (RoadmapSummary & { covers_level: boolean })[];
  };
}

export interface PartySummary {
  id: number;
  name: string;
  description: string;
  visibility: "private" | "public";
  dm: Person;
  member_count: number;
  invited_count: number;
  campaigns: { id: number; name: string; status: CampaignStatus }[];
  created_at: string;
  invited_at?: string;
  /** Party lists only: chat messages others wrote that you haven't read. */
  unread?: number;
  /** The DM's party list only: join requests waiting for an answer. */
  request_count?: number;
}

export interface PartyMember extends Person {
  email?: string;
  status: "invited" | "member";
  invited_at: string;
  joined_at: string | null;
}

export interface Party extends PartySummary {
  role: "dm" | "player";
  members: PartyMember[];
  /** Your friends who aren't in the party yet: the DM can invite them, a member can suggest them. */
  friends: Person[];
  /** DM only: join requests waiting for an answer. */
  requests?: import("./friends").JoinRequest[];
  /** Players only: friends you suggested that the DM hasn't answered yet. */
  suggestions?: import("./friends").JoinRequest[];
}

export const DM_CAMPAIGNS_PATH = "/dm/campaigns/campaigns";
export const DM_PARTIES_PATH = "/dm/campaigns/parties";
export const PLAYER_CAMPAIGNS_PATH = "/play/campaigns/current";
export const PLAYER_PARTIES_PATH = "/play/campaigns/parties";

export const dmCampaignPath = (id: number, page = "overview") => `/dm/campaigns/c/${id}/${page}`;
export const playerCampaignPath = (id: number, page = "overview") => `/play/campaigns/c/${id}/${page}`;
export const dmPartyPath = (id: number) => `${DM_PARTIES_PATH}/${id}`;
export const playerPartyPath = (id: number) => `${PLAYER_PARTIES_PATH}/${id}`;

/** "1 Nov 2026" */
export function longDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** "Level 3 Human Fighter (Champion)" */
export function instanceLine(i: Pick<InstanceSummary, "level" | "race" | "class" | "subclass">): string {
  const cls = i.class ? `${i.class}${i.subclass ? ` (${i.subclass})` : ""}` : null;
  return [`Level ${i.level}`, i.race, cls].filter(Boolean).join(" ");
}
