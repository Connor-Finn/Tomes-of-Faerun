import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { characterPath, type CharacterDetail, type Template } from "../../lib/characters";
import { useFlash } from "../../lib/flash";

/** Character Manager › Create a character: start from a template, or build from scratch. */
export function CreateCharacter() {
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { flash } = useFlash();
  const navigate = useNavigate();

  useEffect(() => {
    void api.get<{ templates: Template[] }>("/api/characters/templates").then((res) => {
      if (res.ok) setTemplates(res.data.templates);
    });
  }, []);

  async function copyTemplate(t: Template) {
    setBusy(t.id);
    setError(null);
    const res = await api.post<CharacterDetail>("/api/characters", { template: t.id });
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
      <h2 id="page-title" className="page-title">
        Create a character
      </h2>
      <p className="page-summary">Write a new character onto a fresh sheet of paper, or copy one that's ready to play.</p>

      <h3 className="leaf-heading">Build your own</h3>
      <div className="path-grid">
        <div className="path-card" data-testid="path-easy">
          <h4>Easy build</h4>
          <p>A guided, step-by-step tutorial. Only the options your character can take are shown, with help along the way. Levels 1 to 3.</p>
          <Link to="/play/characters/new?mode=easy" className="btn primary small">
            Start an Easy build
          </Link>
        </div>
        <div className="path-card" data-testid="path-standard">
          <h4>Standard build</h4>
          <p>Every choice on free tabs you can jump between, levels 1 to 20. Every rule is still enforced.</p>
          <Link to="/play/characters/new?mode=standard" className="btn primary small">
            Start a Standard build
          </Link>
        </div>
      </div>

      <h3 className="leaf-heading">Start from a template</h3>
      <p className="muted">A finished character you copy as your own. Changing your copy never changes the template.</p>
      {error && (
        <p className="form-error-summary" role="alert">
          {error}
        </p>
      )}
      {!templates && <p className="muted">Fetching the templates…</p>}
      <ul className="template-list" data-testid="template-list">
        {templates?.map((t) => (
          <li key={t.id} className="template-card" data-testid="template-card">
            <div>
              <h4 className="template-name">{t.name}</h4>
              <p className="character-line">
                Level {t.level} {t.race} {t.class} · {t.background}
              </p>
              <p className="small">{t.summary}</p>
              <p className="small muted">
                {t.hit_points} hit points · armour class {t.armor_class}
              </p>
            </div>
            <button
              type="button"
              className="btn primary small"
              onClick={() => copyTemplate(t)}
              disabled={busy !== null}
              aria-label={`Use this character: ${t.name}`}
            >
              {busy === t.id ? "Copying…" : "Use this character"}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
