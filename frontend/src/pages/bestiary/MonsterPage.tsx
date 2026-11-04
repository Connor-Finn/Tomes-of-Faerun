import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../../lib/api";
import {
  BESTIARY_PATH,
  MAX_COUNT,
  ROLES,
  ROLE_LABELS,
  collectionPath,
  type CollectionSummary,
  type Environment,
  type MonsterDetail,
  type Role,
} from "../../lib/bestiary";
import { useFlash } from "../../lib/flash";
import { StatBlock } from "./StatBlock";

/** One monster: its stat block, and the DM's controls for saving it. */
export function MonsterPage({ index }: { index: string }) {
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "";
  const [detail, setDetail] = useState<MonsterDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "missing">("loading");

  const load = useCallback(async () => {
    const res = await api.get<MonsterDetail>(`/api/bestiary/monsters/${encodeURIComponent(index)}`);
    if (res.ok) {
      setDetail(res.data);
      setStatus("ok");
    } else {
      setStatus("missing");
    }
  }, [index]);

  useEffect(() => {
    setStatus("loading");
    void load();
  }, [load]);

  const back = (
    <Link to={`${BESTIARY_PATH}${from}`} className="back-link">
      ← Back to the bestiary
    </Link>
  );

  if (status === "missing") {
    return (
      <section aria-labelledby="page-title" data-testid="monster-missing">
        {back}
        <h2 id="page-title" className="page-title">
          No such monster
        </h2>
        <p className="muted">This page of the bestiary is blank. The monster may be spelled differently.</p>
      </section>
    );
  }
  if (!detail) return <p className="muted">Turning to the monster…</p>;

  return (
    <section>
      {back}
      <StatBlock monster={detail.monster} cr={detail.cr} />
      <SavePanel detail={detail} onChange={load} />
    </section>
  );
}

// ---------------------------------------------------------------- saving
function SavePanel({ detail, onChange }: { detail: MonsterDetail; onChange: () => Promise<void> }) {
  const { monster } = detail;
  const { flash } = useFlash();
  const [collections, setCollections] = useState<CollectionSummary[] | null>(null);
  const [environments, setEnvironments] = useState<Environment[] | null>(null);
  const [target, setTarget] = useState<string>("");
  const [newName, setNewName] = useState("");
  const [role, setRole] = useState<Role>("none");
  const [count, setCount] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newEnv, setNewEnv] = useState("");
  const [envError, setEnvError] = useState<string | null>(null);

  const loadLists = useCallback(async () => {
    const [c, e] = await Promise.all([
      api.get<{ collections: CollectionSummary[] }>("/api/bestiary/collections"),
      api.get<{ environments: Environment[] }>("/api/bestiary/environments"),
    ]);
    if (c.ok) {
      setCollections(c.data.collections);
      setTarget((t) => t || (c.data.collections[0] ? String(c.data.collections[0].id) : "new"));
    }
    if (e.ok) setEnvironments(e.data.environments);
  }, []);

  useEffect(() => {
    void loadLists();
  }, [loadLists]);

  async function addToCollection(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    let id = target;
    if (target === "new") {
      const created = await api.post<{ collection: CollectionSummary }>("/api/bestiary/collections", { name: newName });
      if (!created.ok) {
        setBusy(false);
        setError(created.data.errors?.name ?? created.data.error ?? "Couldn't start the collection.");
        return;
      }
      id = String(created.data.collection.id);
      setNewName("");
    }
    const res = await api.post<{ message: string }>(`/api/bestiary/collections/${id}/monsters`, {
      monster: monster.index,
      role,
      count,
    });
    setBusy(false);
    if (!res.ok) {
      setError(res.data.error ?? "Couldn't add the monster.");
      return;
    }
    flash("success", res.data.message);
    setTarget(id);
    setCount(1);
    await Promise.all([onChange(), loadLists()]);
  }

  // Ticked straight away; put back if the server refuses
  const [inEnv, setInEnv] = useState(() => new Set(detail.environments.map((e) => e.id)));
  useEffect(() => setInEnv(new Set(detail.environments.map((e) => e.id))), [detail.environments]);

  async function toggleEnvironment(env: { id: number; name: string }, on: boolean) {
    setInEnv((current) => {
      const next = new Set(current);
      if (on) next.add(env.id);
      else next.delete(env.id);
      return next;
    });
    const url = `/api/bestiary/environments/${env.id}/monsters/${monster.index}`;
    const res = on ? await api.put<{ message: string }>(url) : await api.delete<{ message: string }>(url);
    if (res.ok) flash("success", res.data.message);
    else flash("error", res.data.error ?? "Couldn't change the environment.");
    await onChange();
  }

  async function createEnvironment(e: FormEvent) {
    e.preventDefault();
    setEnvError(null);
    const res = await api.post<{ environment: Environment }>("/api/bestiary/environments", { name: newEnv });
    if (!res.ok) {
      setEnvError(res.data.errors?.name ?? res.data.error ?? "Couldn't make the environment.");
      return;
    }
    setNewEnv("");
    await toggleEnvironment(res.data.environment, true);
    await loadLists();
  }

  return (
    <aside className="save-panel" aria-label="Save this monster">
      <section aria-labelledby="collections-heading" data-testid="save-to-collection">
        <h3 id="collections-heading" className="leaf-heading">
          Collections
        </h3>
        {detail.collections.length > 0 ? (
          <ul className="saved-in" data-testid="saved-in">
            {detail.collections.map((c) => (
              <li key={c.id}>
                <Link to={collectionPath(c.id)}>{c.name}</Link>{" "}
                <span className="muted">
                  {c.count} × <span className={`pill role-${c.role}`}>{ROLE_LABELS[c.role]}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small">Not in any of your collections yet.</p>
        )}

        {collections && (
          <form className="save-form" onSubmit={addToCollection} aria-label="Add to a collection">
            <div className="field">
              <label htmlFor="save-collection">Collection</label>
              <select id="save-collection" value={target} onChange={(e) => setTarget(e.target.value)}>
                {collections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
                <option value="new">New collection…</option>
              </select>
            </div>
            {target === "new" && (
              <div className="field">
                <label htmlFor="save-new-name">New collection name</label>
                <input
                  id="save-new-name"
                  value={newName}
                  maxLength={60}
                  placeholder="Warlock boss dungeon"
                  onChange={(e) => setNewName(e.target.value)}
                />
              </div>
            )}
            <div className="field">
              <label htmlFor="save-role">Role</label>
              <select id="save-role" value={role} onChange={(e) => setRole(e.target.value as Role)}>
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field narrow">
              <label htmlFor="save-count">How many</label>
              <input
                id="save-count"
                type="number"
                min={1}
                max={MAX_COUNT}
                value={count}
                onChange={(e) => setCount(Math.max(1, Math.min(MAX_COUNT, Number(e.target.value) || 1)))}
              />
            </div>
            <button type="submit" className="btn primary small" disabled={busy}>
              Add to collection
            </button>
            {error && (
              <p className="field-error" role="alert" data-testid="save-error">
                {error}
              </p>
            )}
          </form>
        )}
      </section>

      <section aria-labelledby="environments-heading" data-testid="monster-environments">
        <h3 id="environments-heading" className="leaf-heading">
          Environments
        </h3>
        <p className="muted small">Where does it lurk? The rules don't say, so you decide.</p>
        {environments && environments.length > 0 && (
          <fieldset className="env-checks">
            <legend className="sr-only">Environments for {monster.name}</legend>
            {environments.map((env) => (
              <label key={env.id} className="check">
                <input type="checkbox" checked={inEnv.has(env.id)} onChange={(e) => toggleEnvironment(env, e.target.checked)} />
                {env.name}
              </label>
            ))}
          </fieldset>
        )}
        <form className="row wrap inline-form" onSubmit={createEnvironment} aria-label="Make a new environment">
          <label htmlFor="new-env" className="sr-only">
            New environment
          </label>
          <input
            id="new-env"
            value={newEnv}
            maxLength={40}
            placeholder="New environment, e.g. Underdark"
            onChange={(e) => setNewEnv(e.target.value)}
          />
          <button type="submit" className="btn ghost small">
            Add environment
          </button>
        </form>
        {envError && (
          <p className="field-error" role="alert">
            {envError}
          </p>
        )}
      </section>
    </aside>
  );
}
