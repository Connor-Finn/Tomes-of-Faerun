/**
 * Types and paths for friends, people search and joining parties (backend/tof/friends.py and joining.py).
 *
 * Friends make inviting easy: a DM invites a friend from a list instead of typing their email, and a
 * party member can suggest a friend to the DM. Public parties show up in the party search, where any
 * player can ask to join. The party's Dungeon Master always decides.
 */
import type { Person, PartySummary } from "./campaigns";

/** How you're connected to someone: friends, a request you sent, one they sent, or nothing yet. */
export type Relation = "friend" | "sent" | "received" | null;

export interface PersonResult extends Person {
  relation: Relation;
}

export interface FriendRequest extends Person {
  requested_at: string;
}

export interface FriendLists {
  friends: Person[];
  received: FriendRequest[];
  sent: FriendRequest[];
  limit: number;
}

export interface JoinRequest {
  id: number;
  party: { id: number; name: string };
  person: Person;
  /** Set when a party member suggested their friend, rather than the person asking themselves. */
  suggested_by: Person | null;
  message: string;
  created_at: string;
}

/** Where you stand with a public party: in it, invited, waiting on your request, or none of those. */
export type Standing = "member" | "invited" | "requested" | null;

export interface PublicParty extends PartySummary {
  standing: Standing;
  request_id?: number;
  full: boolean;
}

export const FRIENDS_PATH = "/play/campaigns/friends";
export const FIND_PARTY_PATH = "/play/campaigns/find";
export const JOIN_REQUESTS_PATH = "/dm/campaigns/requests";

/** "Mira asked to join" or "Tam suggested their friend Mira" */
export function requestLine(r: JoinRequest): string {
  return r.suggested_by
    ? `${r.suggested_by.name} suggested their friend ${r.person.name}`
    : `${r.person.name} asked to join`;
}
