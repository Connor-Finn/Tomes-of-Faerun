/**
 * Level roadmaps (backend/tof/roadmaps.py): a character's level-ups planned ahead of time.
 *
 * Each planned level is a complete snapshot of the character's levelling choices at that level,
 * so a campaign copy following the roadmap takes the snapshot for the level it's at.
 */
import type { CharacterSummary, CheckResult, Build } from "./characters";

export interface RoadmapSummary {
  id: number;
  name: string;
  character_id: number;
  start_level: number;
  end_level: number;
  /** Campaign copies of the character following this roadmap. */
  followed_by: { campaign: { id: number; name: string }; level: number }[];
  updated_at: string;
}

export interface RoadmapLevel {
  level: number;
  /** The level the roadmap starts at: the character as it is. */
  start: boolean;
  hit_points: number;
  subclass: string | null;
  new_features: string[];
  changes: { slot?: string; label: string; added: string[]; removed: string[] }[];
  /** False when the character has changed since and this level no longer fits the rules. */
  fits: boolean;
  problems: string[];
}

export interface Roadmap extends RoadmapSummary {
  levels: RoadmapLevel[];
}

export interface RoadmapDetail {
  roadmap: Roadmap;
  character: CharacterSummary;
}

/** GET /api/roadmaps/<id>/levels/<n>: the build the builder opens to plan one level. */
export interface RoadmapLevelDetail extends CheckResult {
  roadmap: RoadmapSummary;
  character: CharacterSummary & { build: Build };
  level: number;
  planned: boolean;
  /** Planned levels after this one, which re-planning it clears. */
  later_levels: number;
}

export const MAX_LEVEL = 20;
export const roadmapsPath = (characterId: number) => `/play/characters/c/${characterId}/roadmaps`;
export const roadmapPath = (characterId: number, roadmapId: number) => `${roadmapsPath(characterId)}/${roadmapId}`;
export const planLevelPath = (characterId: number, roadmapId: number, level: number) =>
  `/play/characters/c/${characterId}/roadmaps/${roadmapId}/level/${level}`;

/** "Levels 1 to 6", or "Level 1 only" before anything is planned. */
export function levelRange(r: Pick<RoadmapSummary, "start_level" | "end_level">): string {
  return r.end_level > r.start_level ? `Levels ${r.start_level} to ${r.end_level}` : `Level ${r.start_level} only, nothing planned yet`;
}
