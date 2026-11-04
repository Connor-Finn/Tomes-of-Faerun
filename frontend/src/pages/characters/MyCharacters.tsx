import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { BUILD_MODE_LABELS, characterPath, describe, type CharacterSummary } from "../../lib/characters";

/** Character Manager › My characters: every base character the player owns. */
export function MyCharacters() {
  const [characters, setCharacters] = useState<CharacterSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.get<{ characters: CharacterSummary[] }>("/api/characters").then((res) => {
      if (res.ok) setCharacters(res.data.characters);
      else setError(res.data.error ?? "Couldn't load your characters.");
    });
  }, []);

  return (
    <section aria-labelledby="page-title">
      <div className="row between wrap">
        <h2 id="page-title" className="page-title">
          My characters
        </h2>
        <Link to="/play/characters/create" className="btn primary small">
          Create a character
        </Link>
      </div>
      <p className="page-summary">Your characters as you built them. Campaigns never change these.</p>

      {error && (
        <p className="form-error-summary" role="alert">
          {error}
        </p>
      )}
      {!characters && !error && <p className="muted">Turning the pages…</p>}
      {characters?.length === 0 && (
        <div className="empty-page" data-testid="no-characters">
          <p>No characters yet. Every adventure starts with a blank sheet of paper.</p>
          <Link to="/play/characters/create" className="btn ghost">
            Write your first character
          </Link>
        </div>
      )}
      {characters && characters.length > 0 && (
        <ul className="character-list" data-testid="character-list">
          {characters.map((c) => (
            <li key={c.id} className="character-card" data-testid="character-card">
              <div className="character-crest" aria-hidden="true">
                {(c.name || "?").charAt(0)}
              </div>
              <div className="character-card-body">
                <Link to={characterPath(c.id)} className="character-name">
                  {c.name}
                </Link>
                <p className="character-line">{describe(c)}</p>
                <p className="character-tags">
                  <span className={`pill ${c.status}`} data-testid="character-status">
                    {c.status === "complete" ? "Complete" : "Draft"}
                  </span>
                  <span className="pill mode" data-testid="character-mode">
                    {BUILD_MODE_LABELS[c.build_mode]}
                  </span>
                  {c.background && <span className="muted small">{c.background}</span>}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
