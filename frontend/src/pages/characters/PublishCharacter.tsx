import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import { longDate } from "../../lib/campaigns";
import {
  characterPath,
  describe,
  useCharacterOptions,
  type CharacterDetail,
  type CharacterSummary,
} from "../../lib/characters";
import { useFlash } from "../../lib/flash";
import type { PublishedCharacter } from "../../lib/published";
import { ConfirmDialog } from "../bestiary/ConfirmDialog";

const SUMMARY_MAX = 300;

function copiesLine(n: number): string {
  if (n === 0) return "Not copied yet";
  return n === 1 ? "Copied once" : `Copied ${n} times`;
}

/** "Level 1 Human Fighter · Acolyte" */
function templateLine(p: PublishedCharacter): string {
  const cls = p.class ? `${p.class}${p.subclass ? ` (${p.subclass})` : ""}` : null;
  return `${[`Level ${p.level}`, p.race, cls].filter(Boolean).join(" ")} · ${p.background}`;
}

// ================================================================ Publish a character
/** Character Manager › Publish a character: share a fixed copy other players can start from. */
export function PublishCharacter() {
  const { flash } = useFlash();
  const [params] = useSearchParams();
  const [characters, setCharacters] = useState<CharacterSummary[] | null>(null);
  const [published, setPublished] = useState<PublishedCharacter[] | null>(null);
  const [characterId, setCharacterId] = useState(params.get("character") ?? "");
  const [summary, setSummary] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);
  const [unpublishing, setUnpublishing] = useState<PublishedCharacter | null>(null);

  const loadPublished = useCallback(async () => {
    const res = await api.get<{ published: PublishedCharacter[] }>("/api/published/mine");
    if (res.ok) setPublished(res.data.published);
  }, []);

  useEffect(() => {
    void api.get<{ characters: CharacterSummary[] }>("/api/characters").then((res) => {
      if (res.ok) setCharacters(res.data.characters);
    });
    void loadPublished();
  }, [loadPublished]);

  const finished = characters?.filter((c) => c.status === "complete") ?? [];
  const drafts = characters?.filter((c) => c.status === "draft") ?? [];
  const chosen = finished.find((c) => String(c.id) === characterId) ?? null;

  function review(e: FormEvent) {
    e.preventDefault();
    if (!chosen) {
      setErrors({ character_id: "Choose one of your finished characters." });
      return;
    }
    setConfirming(true);
  }

  async function publish(): Promise<string | void> {
    const res = await api.post<{ message: string; published: PublishedCharacter }>("/api/published", {
      character_id: Number(characterId),
      summary,
    });
    if (!res.ok) {
      setErrors(res.data.errors ?? {});
      setConfirming(false);
      if (!res.data.errors) return res.data.error ?? "The character wasn't published.";
      return;
    }
    flash("success", res.data.message);
    setConfirming(false);
    setSummary("");
    setCharacterId("");
    void loadPublished();
  }

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Publish a character
      </h2>
      <p className="page-summary">
        Share a character as a template. Other players copy it as their own and play it from there.
      </p>

      {characters && finished.length === 0 ? (
        <div className="empty-page" data-testid="nothing-to-publish">
          <p>
            Only finished characters can be published.{" "}
            {drafts.length > 0 ? "Finish one of your drafts first." : "Create a character first."}
          </p>
          <Link to="/play/characters/create" className="btn ghost">
            Create a character
          </Link>
        </div>
      ) : (
        <form className="publish-form" onSubmit={review} aria-label="Publish a character" noValidate>
          <div className="field">
            <label htmlFor="publish-character">Character</label>
            <select
              id="publish-character"
              value={characterId}
              aria-invalid={errors.character_id ? true : undefined}
              aria-describedby={errors.character_id ? "error-character" : undefined}
              onChange={(e) => {
                setCharacterId(e.target.value);
                setErrors({});
              }}
            >
              <option value="">Choose a finished character…</option>
              {finished.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}: {describe(c)}
                </option>
              ))}
            </select>
            {errors.character_id && (
              <p className="field-error" id="error-character" data-testid="error-character">
                {errors.character_id}
              </p>
            )}
            {drafts.length > 0 && (
              <p className="hint">Drafts can't be published until they're finished.</p>
            )}
          </div>
          <div className="field">
            <label htmlFor="publish-summary">Description for other players (optional)</label>
            <textarea
              id="publish-summary"
              rows={3}
              maxLength={SUMMARY_MAX}
              value={summary}
              placeholder="A shield-wall veteran who holds the line so the party's casters don't have to."
              aria-invalid={errors.summary ? true : undefined}
              onChange={(e) => {
                setSummary(e.target.value);
                setErrors({});
              }}
            />
            <p className="hint">
              {summary.length}/{SUMMARY_MAX}
            </p>
            {errors.summary && (
              <p className="field-error" data-testid="error-summary">
                {errors.summary}
              </p>
            )}
          </div>
          <p className="hint" data-testid="roadmap-note">
            Level roadmaps aren't written yet. Once they are, you'll choose which ones to include here.
          </p>
          <button type="submit" className="btn primary">
            Publish…
          </button>
        </form>
      )}

      <h3 className="leaf-heading">Your published characters</h3>
      {published?.length === 0 && (
        <p className="muted" data-testid="no-published">
          You haven't published any characters yet.
        </p>
      )}
      {published && published.length > 0 && (
        <ul className="template-list" data-testid="my-published-list">
          {published.map((p) => (
            <li key={p.id} className="template-card" data-testid="my-published">
              <div>
                <h4 className="template-name">{p.name}</h4>
                <p className="character-line">{templateLine(p)}</p>
                {p.summary && <p className="small">{p.summary}</p>}
                <p className="small muted" data-testid="published-facts">
                  Published {longDate(p.published_at)} · {copiesLine(p.copies)}
                </p>
              </div>
              <div className="row">
                {p.character_id && (
                  <Link to={characterPath(p.character_id)} className="btn ghost small">
                    Open character
                  </Link>
                )}
                <button
                  type="button"
                  className="btn ghost small"
                  aria-label={`Unpublish ${p.name}`}
                  onClick={() => setUnpublishing(p)}
                >
                  Unpublish
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {confirming && chosen && (
        <ConfirmDialog
          title={`Publish ${chosen.name}?`}
          confirmLabel="Publish"
          cancelLabel="Not yet"
          onClose={() => setConfirming(false)}
          onConfirm={publish}
        >
          <p>
            Every player will be able to copy {chosen.name} ({describe(chosen)}) as their own character, including
            its notes. Your author name is shown with it.
          </p>
          <p>
            The template is a fixed copy: editing {chosen.name} later won't change it. You can unpublish it at any
            time, and players keep the copies they've made.
          </p>
        </ConfirmDialog>
      )}
      {unpublishing && (
        <ConfirmDialog
          title={`Unpublish ${unpublishing.name}?`}
          confirmLabel="Unpublish"
          onClose={() => setUnpublishing(null)}
          onConfirm={async () => {
            const res = await api.delete<{ message: string }>(`/api/published/${unpublishing.id}`);
            if (!res.ok) return res.data.error ?? "It wasn't unpublished.";
            flash("info", res.data.message);
            void loadPublished();
          }}
        >
          <p>Other players can no longer copy it. Copies they've already made are theirs to keep, and your own character isn't touched.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}

// ================================================================ Browse published characters
/** Character Manager › Create a character › Published characters: copy another player's template. */
export function PublishedCharacters() {
  const navigate = useNavigate();
  const { flash } = useFlash();
  const options = useCharacterOptions();
  const [query, setQuery] = useState("");
  const [cls, setCls] = useState("");
  const [results, setResults] = useState<PublishedCharacter[] | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const qs = new URLSearchParams();
    if (query.trim()) qs.set("q", query.trim());
    if (cls) qs.set("class", cls);
    let stale = false;
    const timer = window.setTimeout(() => {
      void api.get<{ published: PublishedCharacter[] }>(`/api/published?${qs}`).then((res) => {
        if (stale) return;
        if (res.ok) setResults(res.data.published);
        else setError(res.data.error ?? "Couldn't load the published characters.");
      });
    }, 200);
    return () => {
      stale = true;
      window.clearTimeout(timer);
    };
  }, [query, cls]);

  async function copy(p: PublishedCharacter) {
    setBusy(p.id);
    setError(null);
    const res = await api.post<CharacterDetail>("/api/characters", { published: p.id });
    setBusy(null);
    if (!res.ok) {
      setError(res.data.error ?? "Couldn't copy that character.");
      return;
    }
    flash("success", `${res.data.character.name} joined your characters.`, { afterNavigate: true });
    navigate(characterPath(res.data.character.id));
  }

  return (
    <section aria-labelledby="page-title">
      <Link to="/play/characters/create" className="back-link">
        ← Create a character
      </Link>
      <h2 id="page-title" className="page-title">
        Published characters
      </h2>
      <p className="page-summary">
        Characters other players have shared. Copy one and it becomes your own: changing it never touches theirs.
      </p>

      <form className="row wrap inline-form" role="search" onSubmit={(e) => e.preventDefault()}>
        <div className="field grow">
          <label htmlFor="published-search">Search by name or author</label>
          <input id="published-search" type="search" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="published-class">Class</label>
          <select id="published-class" value={cls} onChange={(e) => setCls(e.target.value)}>
            <option value="">Any class</option>
            {options?.classes.map((c) => (
              <option key={c.index} value={c.index}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </form>

      {error && (
        <p className="form-error-summary" role="alert">
          {error}
        </p>
      )}
      {!results && !error && <p className="muted">Gathering the templates…</p>}
      {results?.length === 0 && (
        <div className="empty-page" data-testid="no-published">
          <p>{query || cls ? "No published characters match." : "Nobody has published a character yet."}</p>
        </div>
      )}
      {results && results.length > 0 && (
        <ul className="template-list" data-testid="published-list">
          {results.map((p) => (
            <li key={p.id} className="template-card" data-testid="published-card">
              <div>
                <h4 className="template-name">{p.name}</h4>
                <p className="character-line">{templateLine(p)}</p>
                <p className="small" data-testid="published-author">
                  Published by {p.mine ? "you" : p.author.name}
                </p>
                {p.summary && <p className="small">{p.summary}</p>}
                <p className="small muted">
                  {p.hit_points} hit points · armour class {p.armor_class} · {copiesLine(p.copies)}
                </p>
              </div>
              <button
                type="button"
                className="btn primary small"
                onClick={() => copy(p)}
                disabled={busy !== null}
                aria-label={`Use this character: ${p.name}`}
              >
                {busy === p.id ? "Copying…" : "Use this character"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
