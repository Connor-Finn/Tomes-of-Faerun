import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, type FieldErrors } from "../../lib/api";
import { BESTIARY_PATH, monsterPath, plural, type Environment } from "../../lib/bestiary";
import { useFlash } from "../../lib/flash";
import { ConfirmDialog } from "./ConfirmDialog";

/**
 * Browse Tomes › Environments: the DM's own map of where monsters live.
 * The SRD doesn't record environments, so these are entirely the DM's.
 */
export function Environments() {
  const { flash } = useFlash();
  const [environments, setEnvironments] = useState<Environment[] | null>(null);
  const [name, setName] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [deleting, setDeleting] = useState<Environment | null>(null);

  const load = useCallback(async () => {
    const res = await api.get<{ environments: Environment[] }>("/api/bestiary/environments");
    if (res.ok) setEnvironments(res.data.environments);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create(e: FormEvent) {
    e.preventDefault();
    const res = await api.post<{ environment: Environment }>("/api/bestiary/environments", { name });
    if (!res.ok) {
      setErrors(res.data.errors ?? { name: res.data.error ?? "Couldn't make the environment." });
      return;
    }
    flash("success", `${res.data.environment.name} was added. Open a monster to say it lives there.`);
    setName("");
    await load();
  }

  async function removeMonster(env: Environment, index: string) {
    const res = await api.delete<{ message: string }>(`/api/bestiary/environments/${env.id}/monsters/${index}`);
    if (res.ok) flash("info", res.data.message);
    else flash("error", res.data.error ?? "The monster wasn't taken out.");
    await load();
  }

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Environments
      </h2>
      <p className="page-summary">
        The rules don't say where monsters live, so draw your own map: the Underdark, a haunted swamp, the warlock's
        tower. Filter the bestiary by any of them.
      </p>

      <form className="row wrap inline-form" onSubmit={create} aria-label="Make a new environment">
        <div className="field grow">
          <label htmlFor="new-environment">New environment</label>
          <input
            id="new-environment"
            value={name}
            maxLength={40}
            placeholder="Underdark"
            aria-invalid={errors.name ? true : undefined}
            onChange={(e) => {
              setName(e.target.value);
              setErrors({});
            }}
          />
        </div>
        <button type="submit" className="btn primary small">
          Add environment
        </button>
      </form>
      {errors.name && (
        <p className="field-error" data-testid="error-name">
          {errors.name}
        </p>
      )}

      {environments?.length === 0 && (
        <div className="empty-page" data-testid="no-environments">
          No environments yet. Add one above, then open monsters in the bestiary and tick where they live.
        </div>
      )}
      {environments && environments.length > 0 && (
        <ul className="environment-list" data-testid="environment-list">
          {environments.map((env) => (
            <li key={env.id} className="environment-card" data-testid="environment-card">
              <div className="row between wrap">
                <h3 className="environment-name">{env.name}</h3>
                <div className="row">
                  <Link to={`${BESTIARY_PATH}?environment=${env.id}`} className="btn ghost small">
                    Browse in the bestiary
                  </Link>
                  <button type="button" className="btn ghost small" aria-label={`Delete ${env.name}`} onClick={() => setDeleting(env)}>
                    Delete
                  </button>
                </div>
              </div>
              <p className="muted small">{plural(env.monster_count, "monster")}</p>
              {env.monsters.length > 0 && (
                <ul className="chips environment-monsters">
                  {env.monsters.map((m) => (
                    <li key={m.index} className="env-monster">
                      <Link to={monsterPath(m.index)}>{m.name}</Link>
                      <span className="muted small">CR {m.cr}</span>
                      <button
                        type="button"
                        className="link-button small"
                        aria-label={`Take ${m.name} out of ${env.name}`}
                        onClick={() => removeMonster(env, m.index)}
                      >
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}

      {deleting && (
        <ConfirmDialog
          title={`Delete ${deleting.name}?`}
          confirmLabel="Delete"
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            const res = await api.delete<{ message: string }>(`/api/bestiary/environments/${deleting.id}`);
            if (!res.ok) return res.data.error ?? "The environment wasn't deleted.";
            flash("info", res.data.message);
            await load();
          }}
        >
          <p>Only the environment goes. Its monsters stay in the bestiary and in your collections.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}
