/**
 * Party chat (backend/tof/chat.py). The browser polls the latest page of messages, so new writing
 * and struck-out messages both show up on their own.
 */
import type { Person } from "./campaigns";

export interface ChatMessage {
  id: number;
  body: string;
  /** null when the writer has since deleted their account. */
  author: Person | null;
  from_dm: boolean;
  mine: boolean;
  can_strike: boolean;
  created_at: string;
}

export interface ChatPage {
  messages: ChatMessage[];
  has_more: boolean;
  /** The last message you'd read before this request (it marks the rest as read). */
  last_read_id: number;
  /** Names of the others writing right now. */
  writing: string[];
}

export const CHAT_POLL_MS = 2000;
export const WRITING_PING_MS = 3000;
export const MESSAGE_MAX = 1000;

/** "20:56" today, "3 Nov, 20:56" otherwise. */
export function chatTime(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === now.toDateString()) return time;
  return `${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}, ${time}`;
}

/** "Mira is writing…", "Mira and Tor are writing…", "3 adventurers are writing…" */
export function writingLine(names: string[]): string {
  if (names.length === 0) return "";
  if (names.length === 1) return `${names[0]} is writing…`;
  if (names.length === 2) return `${names[0]} and ${names[1]} are writing…`;
  return `${names.length} adventurers are writing…`;
}
