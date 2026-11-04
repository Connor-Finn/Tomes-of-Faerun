import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { playerCampaignPath } from "../../lib/campaigns";
import type { CharacterSummary } from "../../lib/characters";
import { useFlash } from "../../lib/flash";
import {
  MAX_LEVEL,
  levelRange,
  planLevelPath,
  roadmapPath,
  roadmapsPath,
  type Roadmap,
  type RoadmapDetail,
  type RoadmapLevel,
  type RoadmapSummary,
} from "../../lib/roadmaps";
import { ConfirmDialog } from "../bestiary/ConfirmDialog";
import { PageHeading } from "../characters/CharacterTome";

/**
 * Character Manager › a character › Roadmaps.
 *
 * A roadmap is a planned route of level-ups. The character itself never levels up here: roadmaps
 * are plans that campaign copies of the character can follow.
 */
export function RoadmapsPage({ character }: { character: CharacterSummary }) {
  const navigate = useNavigate();
  const { flash } = useFlash();
  const [roadmaps, setRoadmaps] = useState<RoadmapSummary[] | null>(null);
  const [limit, setLimit] = useState(10);
  const [canStart, setCanStart] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .get<{ roadmaps: RoadmapSummary[]; limit: number; can_start: boolean }>(`/api/characters/${character.id}/roadmaps`)
      .then((res) => {
        if (!res.ok) return;
        setRoadmaps(res.data.roadmaps);
        setLimit(res.data.limit);
        setCanStart(res.data.can_start);
      });
  }, [character.id]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.post<RoadmapDetail & { message: string }>(`/api/characters/${character.id}/roadmaps`, { name });
    if (!res.ok) {
      setError(res.data.error ?? "The roadmap wasn't started.");
      return;
    }
    flash("success", res.data.message, { afterNavigate: true });
    navigate(roadmapPath(character.id, res.data.roadmap.id));
  }

  return (
    <section aria-labelledby="page-title" data-testid="roadmaps">
      <PageHeading
        title="Roadmaps"
        summary={`Plan ${character.name}'s level-ups ahead of time, one level at a time, up to level ${MAX_LEVEL}. ${character.name} stays at level ${character.level} here; a copy in a campaign can follow a roadmap as it levels up.`}
      />

      {roadmaps && roadmaps.length > 0 && (
        <ul className="roadmap-list" data-testid="roadmap-list">
          {roadmaps.map((r) => (
            <li key={r.id} className="roadmap-card" data-testid="roadmap-card">
              <Link to={roadmapPath(character.id, r.id)} className="roadmap-name">
                {r.name}
              </Link>
              <RoadmapTrack roadmap={r} />
              <p className="small muted">
                {levelRange(r)}
                {r.followed_by.length > 0 && ` · followed in ${r.followed_by.map((f) => f.campaign.name).join(", ")}`}
              </p>
            </li>
          ))}
        </ul>
      )}
      {roadmaps?.length === 0 && canStart && (
        <p className="empty-page" data-testid="no-roadmaps">
          No roadmaps yet. Name one below to start planning.
        </p>
      )}

      {roadmaps && !canStart && (
        <p className="notice" data-testid="roadmaps-unavailable">
          {character.status === "draft"
            ? `Finish ${character.name} in the builder before planning level-ups.`
            : `${character.name} is already level ${MAX_LEVEL}, so there's nothing left to plan.`}
        </p>
      )}
      {roadmaps && canStart && roadmaps.length < limit && (
        <form className="inline-form roadmap-new" onSubmit={onSubmit} aria-label="Start a roadmap">
          <label className="field">
            <span>New roadmap</span>
            <input
              value={name}
              maxLength={60}
              placeholder="Champion route, Healer at heart…"
              onChange={(e) => {
                setName(e.target.value);
                setError(null);
              }}
            />
          </label>
          <button type="submit" className="btn primary">
            Start a roadmap
          </button>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          <p className="hint">
            It starts at level {character.level} with {character.name}'s choices as they are, then you plan each level after
            it in the builder{character.build_mode === "easy" ? ", with Easy build's help" : ""}.
          </p>
        </form>
      )}
    </section>
  );
}

/** Twenty little milestones: filled up to the roadmap's last planned level. */
function RoadmapTrack({ roadmap }: { roadmap: Pick<RoadmapSummary, "start_level" | "end_level"> }) {
  return (
    <ol className="roadmap-track" aria-label={levelRange(roadmap)}>
      {Array.from({ length: MAX_LEVEL }, (_, i) => i + 1).map((lvl) => (
        <li
          key={lvl}
          className={lvl < roadmap.start_level ? "before" : lvl === roadmap.start_level ? "start" : lvl <= roadmap.end_level ? "planned" : ""}
          aria-hidden="true"
        />
      ))}
    </ol>
  );
}

// ================================================================ one roadmap
export function RoadmapPage({ characterId, roadmapId }: { characterId: number; roadmapId: number }) {
  const navigate = useNavigate();
  const { flash } = useFlash();
  const [detail, setDetail] = useState<RoadmapDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [trimming, setTrimming] = useState<number | null>(null);

  const load = useCallback(async () => {
    const res = await api.get<RoadmapDetail>(`/api/roadmaps/${roadmapId}`);
    if (res.ok) setDetail(res.data);
    else setMissing(true);
  }, [roadmapId]);
  useEffect(() => {
    void load();
  }, [load]);

  const back = (
    <Link to={roadmapsPath(characterId)} className="back-link">
      ← All roadmaps
    </Link>
  );
  if (missing) {
    return (
      <section aria-labelledby="page-title" data-testid="roadmap-missing">
        {back}
        <PageHeading title="Roadmap not found" summary="It may have been deleted." />
      </section>
    );
  }
  if (!detail) return <p className="muted">Unrolling the map…</p>;
  const { roadmap, character } = detail;
  const next = roadmap.end_level + 1;

  return (
    <section aria-labelledby="page-title" data-testid="roadmap">
      {back}
      <PageHeading title={roadmap.name} summary={`${levelRange(roadmap)} for ${character.name}.`} />
      <RenameForm roadmap={roadmap} onSaved={setDetail} />
      <RoadmapTrack roadmap={roadmap} />

      {roadmap.followed_by.length > 0 && (
        <p className="notice" data-testid="roadmap-followers">
          Followed by {character.name} in{" "}
          {roadmap.followed_by.map((f, i) => (
            <span key={f.campaign.id}>
              {i > 0 && ", "}
              <Link to={playerCampaignPath(f.campaign.id, "character")}>{f.campaign.name}</Link> (level {f.level})
            </span>
          ))}
          . Changes here apply from their next level-up.
        </p>
      )}

      <ol className="roadmap-levels" data-testid="roadmap-levels">
        {roadmap.levels.map((lvl) => (
          <LevelEntry
            key={lvl.level}
            lvl={lvl}
            last={lvl.level === roadmap.end_level}
            planPath={planLevelPath(characterId, roadmap.id, lvl.level)}
            onTrim={() => setTrimming(lvl.level)}
          />
        ))}
      </ol>

      <div className="row wrap">
        {next <= MAX_LEVEL ? (
          <Link to={planLevelPath(characterId, roadmap.id, next)} className="btn primary" data-testid="plan-next-level">
            Plan level {next}
          </Link>
        ) : (
          <p className="muted">Planned all the way to level {MAX_LEVEL}.</p>
        )}
        <button type="button" className="btn ghost" onClick={() => setDeleting(true)}>
          Delete roadmap
        </button>
      </div>

      {trimming !== null && (
        <ConfirmDialog
          title={`Remove level ${trimming}${trimming < roadmap.end_level ? " and up" : ""}?`}
          confirmLabel="Remove"
          onClose={() => setTrimming(null)}
          onConfirm={async () => {
            const res = await api.delete<RoadmapDetail & { message: string }>(`/api/roadmaps/${roadmap.id}/levels/${trimming}`);
            if (!res.ok) return res.data.error ?? "The levels weren't removed.";
            setDetail(res.data);
            flash("info", res.data.message);
          }}
        >
          <p>
            The roadmap will end at level {trimming - 1}. You can plan the levels again later. Campaign copies following it
            keep the choices they already took.
          </p>
        </ConfirmDialog>
      )}
      {deleting && (
        <ConfirmDialog
          title={`Delete “${roadmap.name}”?`}
          confirmLabel="Delete roadmap"
          onClose={() => setDeleting(false)}
          onConfirm={async () => {
            const res = await api.delete<{ message: string }>(`/api/roadmaps/${roadmap.id}`);
            if (!res.ok) return res.data.error ?? "The roadmap wasn't deleted.";
            flash("info", res.data.message, { afterNavigate: true });
            navigate(roadmapsPath(characterId));
          }}
        >
          <p>
            The plan is gone for good.
            {roadmap.followed_by.length > 0 &&
              ` ${character.name} in ${roadmap.followed_by.map((f) => f.campaign.name).join(", ")} stops following it and keeps the choices taken so far.`}
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}

function LevelEntry({ lvl, last, planPath, onTrim }: { lvl: RoadmapLevel; last: boolean; planPath: string; onTrim: () => void }) {
  return (
    <li className={`roadmap-level${lvl.start ? " start" : ""}${lvl.fits ? "" : " broken"}`} data-testid={`roadmap-level-${lvl.level}`}>
      <span className="roadmap-milestone" aria-hidden="true">
        {lvl.level}
      </span>
      <div className="roadmap-level-body">
        <div className="row between wrap">
          <h3 className="roadmap-level-title">
            Level {lvl.level}
            {lvl.start && <span className="pill">Where it starts</span>}
          </h3>
          <span className="small muted">{lvl.hit_points} HP</span>
        </div>
        {lvl.start ? (
          <p className="small muted">The character as built{lvl.subclass ? `, ${lvl.subclass}` : ""}.</p>
        ) : (
          <>
            {lvl.new_features.length > 0 && (
              <p className="small">
                <strong>Gains</strong> {lvl.new_features.join(", ")}
              </p>
            )}
            {lvl.changes.length > 0 ? (
              <ul className="plain-list roadmap-changes">
                {lvl.changes.map((c) => (
                  <li key={c.slot ?? c.label} className="small">
                    <strong>{c.label}:</strong> {c.added.join(", ")}
                    {c.removed.length > 0 && <span className="muted"> (swapped out {c.removed.join(", ")})</span>}
                  </li>
                ))}
              </ul>
            ) : (
              lvl.new_features.length === 0 && <p className="small muted">No new choices at this level.</p>
            )}
          </>
        )}
        {!lvl.fits && (
          <div className="form-error-summary" role="note">
            <p>This level no longer fits the character (it was changed after planning):</p>
            <ul>
              {lvl.problems.slice(0, 4).map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        )}
        {!lvl.start && (
          <div className="row wrap">
            <Link to={planPath} className="btn ghost small">
              {last ? "Change" : "Re-plan from here"}
            </Link>
            <button type="button" className="btn ghost small" onClick={onTrim}>
              {last ? "Remove" : "Remove this level and up"}
            </button>
          </div>
        )}
      </div>
    </li>
  );
}

function RenameForm({ roadmap, onSaved }: { roadmap: Roadmap; onSaved: (d: RoadmapDetail) => void }) {
  const { flash } = useFlash();
  const [name, setName] = useState(roadmap.name);
  useEffect(() => setName(roadmap.name), [roadmap.name]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.patch<RoadmapDetail & { message: string }>(`/api/roadmaps/${roadmap.id}`, { name });
    if (!res.ok) {
      flash("error", res.data.error ?? "The roadmap wasn't renamed.");
      return;
    }
    onSaved(res.data);
    flash("success", res.data.message);
  }

  return (
    <form className="row wrap roadmap-rename" onSubmit={onSubmit} aria-label="Rename the roadmap">
      <label className="field">
        <span>Name</span>
        <input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
      </label>
      <button type="submit" className="btn ghost small" disabled={name.trim() === roadmap.name || !name.trim()}>
        Rename
      </button>
    </form>
  );
}
