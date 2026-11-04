/**
 * Published characters (backend/tof/published.py): templates players share for others to copy.
 *
 * Publishing takes a snapshot, so the author's later edits never change it. Copying one works like
 * copying a premade template: POST /api/characters {published: id}.
 */
import type { Person } from "./campaigns";
import type { Template } from "./characters";

export interface PublishedCharacter extends Omit<Template, "id"> {
  id: number;
  author: Person;
  mine: boolean;
  class_index: string | null;
  subclass: string | null;
  copies: number;
  /** Your own publications only: the character it was published from (null once deleted). */
  character_id: number | null;
  published_at: string;
}

export const PUBLISH_PATH = "/play/characters/publish";
export const PUBLISHED_BROWSE_PATH = "/play/characters/create/published";
