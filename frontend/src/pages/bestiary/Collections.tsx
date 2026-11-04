import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type FieldErrors } from "../../lib/api";
import {
  BESTIARY_PATH,
  COLLECTIONS_PATH,
  MAX_COUNT,
  ROLES,
  collectionPath,
  monsterPath,
  plural,
  xp,
  type Collection,
  type CollectionEntry,
  type CollectionSummary,
  type Role,
} from "../../lib/bestiary";
import { useFlash } from "../../lib/flash";
import { ConfirmDialog } from "./ConfirmDialog";

/** Browse Tomes › Monster collections: the DM's groups of monsters, or one of them. */
export function Collections() {
  const { sub } = useParams();
  return sub ? <CollectionPage id={Number(sub)} /> : <CollectionList />;
}

function RoleTally({ roles }: { roles: CollectionSummary["roles"] }) {
  const parts = ROLES.filter((r) => r.value !== "none" && roles[r.value] > 0);
  if (!parts.length) return null;
  return (
    <span className="role-tally">
      {parts.map((r) => (
        <span key={r.value} className={`pill role-${r.value}`}>
          {roles[r.value]} {r.label.toLowerCase()}
          {roles[r.value] === 1 ? "" : r.value === "boss" ? "es" : "s"}
        </span>
      ))}
    </span>
  );
}

// ---------------------------------------------------------------- the list
function CollectionList() {
  const navigate = useNavigate();
  const { flash } = useFlash();
  const [collections, setCollections] = useState<CollectionSummary[] | null>(null);
  const [name, setName] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    void api.get<{ collections: CollectionSummary[] }>("/api/bestiary/collections").then((res) => {
      if (res.ok) setCollections(res.data.collections);
      else setLoadError(res.data.error ?? "Couldn't load your collections.");
    });
  }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    const res = await api.post<{ collection: Collection }>("/api/bestiary/collections", { name });
    if (!res.ok) {
      setErrors(res.data.errors ?? { name: res.data.error ?? "Couldn't start the collection." });
      return;
    }
    flash("success", `${res.data.collection.name} is ready. Add monsters from the bestiary.`, { afterNavigate: true });
    navigate(collectionPath(res.data.collection.id));
  }

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Monster collections
      </h2>
      <p className="page-summary">
        Gather monsters for a dungeon, a lair or a single fight, and mark which are the minions and which is the boss.
      </p>

      <form className="row wrap inline-form" onSubmit={create} aria-label="Start a new collection">
        <div className="field grow">
          <label htmlFor="new-collection">New collection</label>
          <input
            id="new-collection"
            value={name}
            maxLength={60}
            placeholder="Warlock boss dungeon"
            aria-invalid={errors.name ? true : undefined}
            aria-describedby={errors.name ? "new-collection-error" : undefined}
            onChange={(e) => {
              setName(e.target.value);
              setErrors({});
            }}
          />
        </div>
        <button type="submit" className="btn primary small">
          Start collection
        </button>
      </form>
      {errors.name && (
        <p className="field-error" id="new-collection-error" data-testid="error-name">
          {errors.name}
        </p>
      )}

      {loadError && (
        <p className="form-error-summary" role="alert">
          {loadError}
        </p>
      )}
      {collections?.length === 0 && (
        <div className="empty-page" data-testid="no-collections">
          <p>No collections yet. Start one above, or open any monster in the bestiary and add it to a new one.</p>
          <Link to={BESTIARY_PATH} className="btn ghost">
            Open the bestiary
          </Link>
        </div>
      )}
      {collections && collections.length > 0 && (
        <ul className="collection-list" data-testid="collection-list">
          {collections.map((c) => (
            <li key={c.id} className="collection-card" data-testid="collection-card">
              <Link to={collectionPath(c.id)} className="collection-name">
                {c.name}
              </Link>
              <p className="muted small" data-testid="collection-totals">
                {plural(c.monster_count, "monster")} · {xp(c.total_xp)}
              </p>
              <RoleTally roles={c.roles} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- one collection
function CollectionPage({ id }: { id: number }) {
  const navigate = useNavigate();
  const { flash } = useFlash();
  const [collection, setCollection] = useState<Collection | null>(null);
  const [missing, setMissing] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    const res = await api.get<{ collection: Collection }>(`/api/bestiary/collections/${id}`);
    if (res.ok) setCollection(res.data.collection);
    else setMissing(true);
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const back = (
    <Link to={COLLECTIONS_PATH} className="back-link">
      ← All collections
    </Link>
  );

  if (missing) {
    return (
      <section aria-labelledby="page-title" data-testid="collection-missing">
        {back}
        <h2 id="page-title" className="page-title">
          Collection not found
        </h2>
        <p className="muted">It may have been deleted, or it belongs to another Dungeon Master.</p>
      </section>
    );
  }
  if (!collection) return <p className="muted">Gathering the monsters…</p>;

  async function patchEntry(entry: CollectionEntry, changes: Partial<{ role: Role; count: number; note: string }>) {
    const res = await api.patch<{ collection: Collection }>(`/api/bestiary/collections/${id}/monsters/${entry.id}`, changes);
    if (res.ok) setCollection(res.data.collection);
    else flash("error", res.data.error ?? "That change wasn't saved.");
  }

  async function remove(entry: CollectionEntry) {
    const res = await api.delete<{ collection: Collection; message: string }>(`/api/bestiary/collections/${id}/monsters/${entry.id}`);
    if (res.ok) {
      setCollection(res.data.collection);
      flash("info", res.data.message);
    } else {
      flash("error", res.data.error ?? "The monster wasn't removed.");
    }
  }

  const groups = ROLES.map((r) => ({ ...r, entries: collection.entries.filter((e) => e.role === r.value) })).filter(
    (g) => g.entries.length > 0,
  );

  return (
    <section aria-labelledby="page-title" data-testid="collection">
      {back}
      {renaming ? (
        <RenameForm collection={collection} onDone={(c) => (c && setCollection(c), setRenaming(false))} />
      ) : (
        <div className="row between wrap">
          <h2 id="page-title" className="page-title">
            {collection.name}
          </h2>
          <div className="row">
            <button type="button" className="btn ghost small" onClick={() => setRenaming(true)}>
              Rename
            </button>
            <button type="button" className="btn ghost small" onClick={() => setDeleting(true)}>
              Delete collection
            </button>
          </div>
        </div>
      )}
      <p className="page-summary" data-testid="collection-totals">
        {plural(collection.monster_count, "monster")} · {xp(collection.total_xp)} in all
      </p>

      {collection.entries.length === 0 ? (
        <div className="empty-page" data-testid="empty-collection">
          <p>No monsters yet. Open one in the bestiary and choose “Add to collection”.</p>
          <Link to={BESTIARY_PATH} className="btn ghost">
            Find monsters
          </Link>
        </div>
      ) : (
        <>
          {groups.map((g) => (
            <div key={g.value} className="role-group" data-testid={`role-group-${g.value}`}>
              <h3 className="leaf-heading">
                {g.value === "none" ? "Without a role" : g.value === "boss" ? "Bosses" : `${g.label}s`}
              </h3>
              <ul className="entry-list">
                {g.entries.map((entry) => (
                  <EntryRow key={entry.id} entry={entry} onChange={(c) => patchEntry(entry, c)} onRemove={() => remove(entry)} />
                ))}
              </ul>
            </div>
          ))}
          <p className="row wrap">
            <Link to={BESTIARY_PATH} className="btn ghost small">
              Add more monsters
            </Link>
          </p>
        </>
      )}

      <NotesForm collection={collection} onSaved={setCollection} />

      {deleting && (
        <ConfirmDialog
          title={`Delete ${collection.name}?`}
          confirmLabel="Delete"
          onClose={() => setDeleting(false)}
          onConfirm={async () => {
            const res = await api.delete<{ message: string }>(`/api/bestiary/collections/${id}`);
            if (!res.ok) return res.data.error ?? "The collection wasn't deleted.";
            flash("info", res.data.message, { afterNavigate: true });
            navigate(COLLECTIONS_PATH);
          }}
        >
          <p>The collection and its notes are gone for good. The monsters stay in the bestiary.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}

function EntryRow({
  entry,
  onChange,
  onRemove,
}: {
  entry: CollectionEntry;
  onChange: (changes: Partial<{ role: Role; count: number }>) => void;
  onRemove: () => void;
}) {
  const m = entry.monster;
  const [count, setCount] = useState(String(entry.count));
  useEffect(() => setCount(String(entry.count)), [entry.count]);

  function commitCount() {
    const n = Math.round(Number(count));
    if (!Number.isFinite(n) || n < 1 || n > MAX_COUNT) {
      setCount(String(entry.count));
      return;
    }
    if (n !== entry.count) onChange({ count: n });
  }

  return (
    <li className="entry" data-testid="collection-entry">
      <div className="entry-main">
        <Link to={monsterPath(m.index)} className="monster-name">
          {m.name}
        </Link>
        <span className="muted small">
          CR {m.cr} · {m.size} {m.type} · {xp(entry.xp)}
        </span>
      </div>
      <div className="entry-controls">
        <label className="compact">
          <span>How many</span>
          <input
            type="number"
            min={1}
            max={MAX_COUNT}
            value={count}
            aria-label={`How many ${m.name}`}
            onChange={(e) => setCount(e.target.value)}
            onBlur={commitCount}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), commitCount())}
          />
        </label>
        <label className="compact">
          <span>Role</span>
          <select value={entry.role} aria-label={`Role of ${m.name}`} onChange={(e) => onChange({ role: e.target.value as Role })}>
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn ghost small" aria-label={`Remove ${m.name}`} onClick={onRemove}>
          Remove
        </button>
      </div>
    </li>
  );
}

function RenameForm({ collection, onDone }: { collection: Collection; onDone: (c?: Collection) => void }) {
  const [name, setName] = useState(collection.name);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.patch<{ collection: Collection }>(`/api/bestiary/collections/${collection.id}`, { name });
    if (res.ok) onDone(res.data.collection);
    else setError(res.data.errors?.name ?? res.data.error ?? "The name wasn't saved.");
  }

  return (
    <form className="row wrap inline-form" onSubmit={onSubmit} aria-label="Rename the collection">
      <div className="field grow">
        <label htmlFor="rename-collection">Collection name</label>
        <input id="rename-collection" value={name} maxLength={60} autoFocus onChange={(e) => setName(e.target.value)} />
        {error && (
          <p className="field-error" data-testid="error-name">
            {error}
          </p>
        )}
      </div>
      <button type="submit" className="btn primary small">
        Save name
      </button>
      <button type="button" className="btn ghost small" onClick={() => onDone()}>
        Cancel
      </button>
    </form>
  );
}

function NotesForm({ collection, onSaved }: { collection: Collection; onSaved: (c: Collection) => void }) {
  const { flash } = useFlash();
  const [notes, setNotes] = useState(collection.notes);
  const changed = notes !== collection.notes;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.patch<{ collection: Collection }>(`/api/bestiary/collections/${collection.id}`, { notes });
    if (res.ok) {
      onSaved(res.data.collection);
      flash("success", "Notes saved.");
    } else {
      flash("error", res.data.errors?.notes ?? res.data.error ?? "The notes weren't saved.");
    }
  }

  return (
    <form className="notes-form" onSubmit={onSubmit} aria-label="Collection notes">
      <h3 className="leaf-heading">
        <label htmlFor="collection-notes">DM notes</label>
      </h3>
      <textarea
        id="collection-notes"
        rows={4}
        maxLength={2000}
        value={notes}
        placeholder="Tactics, treasure, where the boss waits…"
        onChange={(e) => setNotes(e.target.value)}
      />
      <div className="row end">
        <button type="submit" className="btn primary small" disabled={!changed}>
          Save notes
        </button>
      </div>
    </form>
  );
}
