import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { Breadcrumbs, Tome } from "../../components/Tome";
import { api } from "../../lib/api";
import {
  BUILD_MODE_LABELS,
  NOTE_LABELS,
  characterPath,
  describe,
  signed,
  useCharacter,
  type BuildMode,
  type CharacterDetail,
  type NoteField,
  type Sheet,
} from "../../lib/characters";
import { useFlash } from "../../lib/flash";
import { MODE_LABELS, useEnterMode } from "../../lib/mode";
import { useFavouriteSpells } from "../../lib/spells";
import { FavouriteStar, SpellReader } from "../spells/SpellText";

/** Every character opens as its own tome. */
export const CHARACTER_PAGES = [
  { slug: "sheet", title: "Character sheet" },
  { slug: "spellbook", title: "Spellbook" },
  { slug: "inventory", title: "Inventory" },
  { slug: "features", title: "Features" },
  { slug: "notes", title: "Notes" },
  { slug: "campaigns", title: "Campaigns" },
  { slug: "roadmaps", title: "Roadmaps" },
];

export function CharacterTome() {
  const { id, page: slug } = useParams();
  const characterId = Number(id);
  useEnterMode("player");
  const { detail, status, replace } = useCharacter(characterId);

  if (!slug) return <Navigate to={characterPath(characterId)} replace />;
  const trail = [
    { label: "Guild Hall", to: "/guild-hall" },
    { label: MODE_LABELS.player, to: "/guild-hall" },
    { label: "Character Manager", to: "/play/characters/my-characters" },
  ];

  if (status === "missing" || status === "error") {
    return (
      <>
        <Breadcrumbs trail={[...trail, { label: "Missing" }]} />
        <div className="card narrow center" data-testid="character-missing">
          <h1>Character not found</h1>
          <p className="muted">It may have been deleted, or it belongs to someone else.</p>
          <Link to="/play/characters/my-characters" className="btn ghost">
            Back to my characters
          </Link>
        </div>
      </>
    );
  }
  if (!detail) return <p className="muted center">Opening the tome…</p>;

  const { character, sheet } = detail;
  const page = CHARACTER_PAGES.find((p) => p.slug === slug);

  return (
    <>
      <Breadcrumbs trail={[...trail, { label: character.name }]} />
      <Tome
        eyebrow="Character Manager"
        title={character.name}
        subtitle={describe(character)}
        basePath={`/play/characters/c/${character.id}`}
        pages={CHARACTER_PAGES}
        current={page?.slug}
        cover="oxblood"
        aside={<CharacterControls detail={detail} onChange={replace} />}
      >
        {!page && <MissingCharacterPage id={character.id} />}
        {page?.slug === "sheet" && <SheetPage detail={detail} />}
        {page?.slug === "spellbook" && <SpellbookPage sheet={sheet} characterId={detail.character.id} />}
        {page?.slug === "inventory" && <InventoryPage sheet={sheet} />}
        {page?.slug === "features" && <FeaturesPage sheet={sheet} />}
        {page?.slug === "notes" && <NotesPage detail={detail} onSaved={replace} />}
        {page?.slug === "campaigns" && (
          <PlannedPage
            title="Campaigns"
            summary="The campaigns this character is playing in."
            plans={[
              "Each campaign keeps its own copy of the character (an instance) with its level, hit points, items and spells.",
              "This page lists those instances. The character here never changes.",
            ]}
          />
        )}
        {page?.slug === "roadmaps" && (
          <PlannedPage
            title="Roadmaps"
            summary="Plan this character's level-ups ahead of time."
            plans={[
              "Named roadmaps of level choices (subclass, spells, ability scores) up to level 20.",
              "Keep several, edit them and delete them.",
              "A campaign instance can follow a roadmap when it levels up.",
            ]}
          />
        )}
      </Tome>
    </>
  );
}

// ---------------------------------------------------------------- controls
function CharacterControls({ detail, onChange }: { detail: CharacterDetail; onChange: (d: CharacterDetail) => void }) {
  const { character } = detail;
  const { flash } = useFlash();
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // Shown straight away; put back if the server refuses
  const [shownMode, setShownMode] = useState<BuildMode>(character.build_mode);
  useEffect(() => setShownMode(character.build_mode), [character.build_mode]);

  async function setMode(mode: BuildMode) {
    if (mode === character.build_mode) return;
    setShownMode(mode);
    setSaving(true);
    const res = await api.patch<CharacterDetail>(`/api/characters/${character.id}`, { build_mode: mode });
    setSaving(false);
    if (res.ok) {
      onChange(res.data);
      flash("success", `${character.name} now uses ${BUILD_MODE_LABELS[mode]}.`);
    } else {
      setShownMode(character.build_mode);
      flash("error", res.data.error ?? "Couldn't change the build mode.");
    }
  }

  return (
    <div className="character-controls">
      <fieldset className="build-mode" data-testid="build-mode" aria-busy={saving}>
        <legend>Build mode</legend>
        {(["easy", "standard"] as BuildMode[]).map((mode) => (
          <label key={mode} className="check">
            <input
              type="radio"
              name="build_mode"
              value={mode}
              checked={shownMode === mode}
              onChange={() => setMode(mode)}
            />
            {BUILD_MODE_LABELS[mode]}
          </label>
        ))}
        <p className="hint">
          Easy build shows only the options this character can take, with help along the way. It only changes how
          choices are shown, never the character.
        </p>
      </fieldset>
      <div className="row wrap">
        <Link to={`/play/characters/c/${character.id}/edit`} className="btn primary small">
          Edit in the builder
        </Link>
        <button type="button" className="btn ghost small" onClick={() => setDeleting(true)}>
          Delete character
        </button>
      </div>
      {deleting && <DeleteCharacterDialog name={character.name} id={character.id} onClose={() => setDeleting(false)} />}
    </div>
  );
}

function DeleteCharacterDialog({ id, name, onClose }: { id: number; name: string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const navigate = useNavigate();
  const { flash } = useFlash();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.delete<{ message: string }>(`/api/characters/${id}`);
    if (!res.ok) {
      setError(res.data.error ?? "The character wasn't deleted.");
      return;
    }
    flash("info", res.data.message, { afterNavigate: true });
    navigate("/play/characters/my-characters");
  }

  return (
    <dialog ref={ref} className="modal" aria-labelledby="delete-character-title" onClose={onClose}>
      <form onSubmit={onSubmit}>
        <h2 id="delete-character-title">Delete {name}?</h2>
        <p>The character sheet is burned for good. This can't be undone.</p>
        {error && (
          <p className="form-error-summary" role="alert">
            {error}
          </p>
        )}
        <div className="row end">
          <button type="button" className="btn ghost" onClick={() => ref.current?.close()}>
            Keep it
          </button>
          <button type="submit" className="btn danger">
            Delete {name}
          </button>
        </div>
      </form>
    </dialog>
  );
}

// ---------------------------------------------------------------- pages
function PageHeading({ title, summary }: { title: string; summary?: string }) {
  return (
    <>
      <h2 id="page-title" className="page-title">
        {title}
      </h2>
      {summary && <p className="page-summary">{summary}</p>}
    </>
  );
}

function DraftNotice({ detail }: { detail: CharacterDetail }) {
  if (detail.complete) return null;
  const shown = detail.missing.slice(0, 6);
  return (
    <div className="draft-notice" role="note" data-testid="draft-notice">
      <span className="badge">Draft</span>
      <p>
        <strong>This character isn't finished.</strong> The sheet shows what's decided so far.
      </p>
      <ul className="plans">
        {shown.map((m) => (
          <li key={m.field}>{m.message}</li>
        ))}
        {detail.missing.length > shown.length && <li>…and {detail.missing.length - shown.length} more.</li>}
      </ul>
      <Link to={`/play/characters/c/${detail.character.id}/edit`} className="btn ghost small">
        Continue building
      </Link>
    </div>
  );
}

function SheetPage({ detail }: { detail: CharacterDetail }) {
  const { sheet } = detail;
  const s = sheet.summary;
  const stats = [
    { label: "Armour class", value: sheet.armor_class, note: sheet.armor_class_note, id: "ac" },
    { label: "Hit points", value: sheet.hit_points, note: sheet.hit_points_note ?? `Hit dice ${sheet.hit_dice}`, id: "hp" },
    { label: "Speed", value: `${sheet.speed} ft`, id: "speed" },
    { label: "Initiative", value: signed(sheet.initiative), id: "initiative" },
    { label: "Proficiency bonus", value: signed(sheet.proficiency_bonus), id: "proficiency" },
    { label: "Passive Perception", value: sheet.passive_perception, id: "passive-perception" },
  ];
  return (
    <section aria-labelledby="page-title" className="sheet" data-testid="character-sheet">
      <PageHeading title="Character sheet" />
      <DraftNotice detail={detail} />
      <dl className="sheet-identity">
        {[
          ["Race", s.subrace ?? s.race],
          ["Class", s.class ? `${s.class}${s.subclass ? ` (${s.subclass})` : ""}` : null],
          ["Level", s.level],
          ["Background", s.background],
          ["Alignment", s.alignment],
        ].map(([label, value]) => (
          <div key={label as string}>
            <dt>{label}</dt>
            <dd>{value ?? "—"}</dd>
          </div>
        ))}
      </dl>

      <ul className="stat-row" aria-label="Combat statistics">
        {stats.map((st) => (
          <li key={st.id} className="stat" data-testid={`stat-${st.id}`}>
            <span className="stat-value">{st.value}</span>
            <span className="stat-label">{st.label}</span>
            {st.note && <span className="stat-note">{st.note}</span>}
          </li>
        ))}
      </ul>

      <h3 className="leaf-heading">Abilities</h3>
      <ul className="ability-row" aria-label="Ability scores">
        {sheet.abilities.map((a) => (
          <li key={a.key} className="ability" data-testid={`ability-${a.key}`}>
            <abbr className="ability-name" title={a.name}>
              {a.key.toUpperCase()}
            </abbr>
            <span className="ability-mod">{signed(a.modifier)}</span>
            <span className="ability-score">{a.score}</span>
          </li>
        ))}
      </ul>

      <div className="sheet-columns">
        <div>
          <h3 className="leaf-heading">Saving throws</h3>
          <ul className="check-list" aria-label="Saving throws">
            {sheet.abilities.map((a) => (
              <li key={a.key} data-testid={`save-${a.key}`}>
                <span className={`prof-dot${a.save_proficient ? " on" : ""}`} aria-label={a.save_proficient ? "Proficient" : undefined} />
                <span className="check-bonus">{signed(a.save)}</span> {a.name}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="leaf-heading">Skills</h3>
          <ul className="check-list" aria-label="Skills">
            {sheet.skills.map((sk) => (
              <li key={sk.index} data-testid={`skill-${sk.index}`}>
                <span
                  className={`prof-dot${sk.proficient ? " on" : ""}${sk.expertise ? " double" : ""}`}
                  aria-label={sk.expertise ? "Expertise" : sk.proficient ? "Proficient" : undefined}
                />
                <span className="check-bonus">{signed(sk.bonus)}</span> {sk.name}{" "}
                <span className="muted small">({sk.ability.toUpperCase()})</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <h3 className="leaf-heading">Attacks</h3>
      {sheet.attacks.length === 0 ? (
        <p className="muted">No weapons.</p>
      ) : (
        <div className="table-wrap">
          <table data-testid="attacks">
            <thead>
              <tr>
                <th scope="col">Weapon</th>
                <th scope="col">To hit</th>
                <th scope="col">Damage</th>
                <th scope="col">Range</th>
              </tr>
            </thead>
            <tbody>
              {sheet.attacks.map((w) => (
                <tr key={w.index}>
                  <td>
                    {w.name}
                    {!w.proficient && <span className="muted small"> (not proficient)</span>}
                  </td>
                  <td>{signed(w.attack_bonus)}</td>
                  <td>
                    {w.damage} {w.damage_type.toLowerCase()}
                  </td>
                  <td>{w.range}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 className="leaf-heading">Proficiencies and languages</h3>
      <dl className="prof-list">
        <dt>Armour</dt>
        <dd>{sheet.proficiencies.armor.join(", ") || "None"}</dd>
        <dt>Weapons</dt>
        <dd>{sheet.proficiencies.weapons.join(", ") || "None"}</dd>
        <dt>Tools</dt>
        <dd>{sheet.proficiencies.tools.join(", ") || "None"}</dd>
        <dt>Languages</dt>
        <dd data-testid="languages">{sheet.languages.join(", ") || "None"}</dd>
      </dl>
    </section>
  );
}

const ORDINAL = ["Cantrips", "1st level", "2nd level", "3rd level", "4th level", "5th level", "6th level", "7th level", "8th level", "9th level"];

function SpellbookPage({ sheet, characterId }: { sheet: Sheet; characterId: number }) {
  const sc = sheet.spellcasting;
  const [reading, setReading] = useState<string | null>(null);
  const { isFavourite, toggle } = useFavouriteSpells();
  if (!sc) {
    return (
      <section aria-labelledby="page-title">
        <PageHeading title="Spellbook" />
        <p className="empty-page" data-testid="no-spells">
          {sheet.summary.name} doesn't cast spells. Not every hero needs magic.
        </p>
      </section>
    );
  }
  const levels = [...new Set(sc.spells.map((s) => s.level))].sort((a, b) => a - b);
  return (
    <section aria-labelledby="page-title" data-testid="spellbook">
      <PageHeading title="Spellbook" />
      <div className="row between wrap">
        <p className="muted small">Open a spell to read it. Stars mark your favourite spells.</p>
        <Link to={`/play/characters/c/${characterId}/edit?section=spells`} className="btn ghost small">
          Change spells
        </Link>
      </div>
      <ul className="stat-row" aria-label="Spellcasting">
        <li className="stat">
          <span className="stat-value">{sc.ability_name.slice(0, 3).toUpperCase()}</span>
          <span className="stat-label">Spellcasting ability</span>
        </li>
        <li className="stat" data-testid="stat-spell-dc">
          <span className="stat-value">{sc.save_dc}</span>
          <span className="stat-label">Spell save DC</span>
        </li>
        <li className="stat" data-testid="stat-spell-attack">
          <span className="stat-value">{signed(sc.attack_bonus)}</span>
          <span className="stat-label">Spell attack</span>
        </li>
      </ul>
      {Object.keys(sc.slots).length > 0 && (
        <p data-testid="spell-slots">
          <strong>Spell slots: </strong>
          {Object.entries(sc.slots)
            .map(([lvl, n]) => `${n} × ${ORDINAL[Number(lvl)]}`)
            .join(", ")}
        </p>
      )}
      {sc.spells.length === 0 && <p className="muted">No spells chosen yet.</p>}
      {levels.map((lvl) => (
        <div key={lvl}>
          <h3 className="leaf-heading">{ORDINAL[lvl]}</h3>
          <ul className="spell-list">
            {sc.spells
              .filter((s) => s.level === lvl)
              .map((s) => (
                <li key={s.index} data-testid="spell">
                  <FavouriteStar name={s.name} on={isFavourite(s.index)} onToggle={() => void toggle(s.index)} />
                  <button
                    type="button"
                    className="spell-name link-like"
                    aria-expanded={reading === s.index}
                    onClick={() => setReading((r) => (r === s.index ? null : s.index))}
                  >
                    {s.name}
                  </button>{" "}
                  <span className="muted small">{s.school}</span>
                  <span className="spell-tags">
                    {s.source !== "Cantrip" && s.source !== "Known" && s.source !== "Prepared" && s.source !== "Spellbook" && (
                      <span className="pill">{s.source}</span>
                    )}
                    {s.level > 0 && s.prepared && sc.spells.some((x) => x.source === "Spellbook") && (
                      <span className="pill active">Prepared</span>
                    )}
                  </span>
                  {reading === s.index && <SpellReader index={s.index} />}
                </li>
              ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function InventoryPage({ sheet }: { sheet: Sheet }) {
  const weight = sheet.inventory.reduce((sum, i) => sum + (i.weight ?? 0) * i.quantity, 0);
  return (
    <section aria-labelledby="page-title" data-testid="inventory">
      <PageHeading title="Inventory" />
      <p>
        <strong>Gold:</strong> <span data-testid="gold">{sheet.gold} gp</span> · <strong>Carrying:</strong> {weight} lb
      </p>
      {sheet.inventory.length === 0 ? (
        <p className="muted">Nothing but the clothes on their back.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col">Qty</th>
                <th scope="col">Type</th>
                <th scope="col">Weight</th>
              </tr>
            </thead>
            <tbody>
              {sheet.inventory.map((i) => (
                <tr key={i.index} data-testid="inventory-item">
                  <td>
                    {i.name} {i.equipped && <span className="pill active">Equipped</span>}
                    {i.contents.length > 0 && (
                      <details className="pack-contents">
                        <summary>What's inside</summary>
                        <p className="small">{i.contents.map((c) => `${c.quantity} × ${c.name}`).join(", ")}</p>
                      </details>
                    )}
                  </td>
                  <td>{i.quantity}</td>
                  <td>{i.category}</td>
                  <td>{i.weight != null ? `${i.weight * i.quantity} lb` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

const SOURCE_LABELS: Record<string, string> = {
  race: "Racial traits",
  background: "Background",
  class: "Class features",
  subclass: "Subclass features",
  feat: "Feats",
};

function FeaturesPage({ sheet }: { sheet: Sheet }) {
  const groups = Object.keys(SOURCE_LABELS).filter((g) => sheet.features.some((f) => f.source === g));
  return (
    <section aria-labelledby="page-title" data-testid="features">
      <PageHeading title="Features" summary="Everything your race, background and class let you do." />
      {groups.length === 0 && <p className="muted">Choose a race, class and background to see your features.</p>}
      {groups.map((g) => (
        <div key={g}>
          <h3 className="leaf-heading">{SOURCE_LABELS[g]}</h3>
          {sheet.features
            .filter((f) => f.source === g)
            .map((f) => (
              <details key={f.index} className="feature" data-testid="feature">
                <summary>
                  <span className="feature-name">{f.name}</span>
                  {g !== "race" && g !== "background" && <span className="muted small"> · level {f.level}</span>}
                </summary>
                {f.desc.map((d, i) => (
                  <p key={i}>{d}</p>
                ))}
              </details>
            ))}
        </div>
      ))}
    </section>
  );
}

function NotesPage({ detail, onSaved }: { detail: CharacterDetail; onSaved: (d: CharacterDetail) => void }) {
  const { flash } = useFlash();
  const [notes, setNotes] = useState(detail.sheet.notes);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = JSON.stringify(notes) !== JSON.stringify(detail.sheet.notes);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const res = await api.patch<CharacterDetail>(`/api/characters/${detail.character.id}`, { notes });
    setSaving(false);
    if (!res.ok) {
      const problems = (res.data as unknown as { errors?: { message: string }[] }).errors;
      setError(problems?.[0]?.message ?? res.data.error ?? "Notes not saved.");
      return;
    }
    onSaved(res.data);
    flash("success", "Notes saved.");
  }

  return (
    <section aria-labelledby="page-title">
      <PageHeading title="Notes" summary="Who your character is, beyond the numbers." />
      <form onSubmit={onSubmit} className="notes-form">
        {error && (
          <p className="form-error-summary" role="alert">
            {error}
          </p>
        )}
        {(Object.keys(NOTE_LABELS) as NoteField[]).map((key) => (
          <div className="field" key={key}>
            <label htmlFor={`note-${key}`}>{NOTE_LABELS[key]}</label>
            <textarea
              id={`note-${key}`}
              name={key}
              rows={key === "backstory" ? 6 : 2}
              maxLength={2000}
              value={notes[key]}
              onChange={(e) => setNotes((n) => ({ ...n, [key]: e.target.value }))}
            />
          </div>
        ))}
        <div className="row end">
          <button type="submit" className="btn primary" disabled={!dirty || saving}>
            {saving ? "Saving…" : "Save notes"}
          </button>
        </div>
      </form>
    </section>
  );
}

function PlannedPage({ title, summary, plans }: { title: string; summary: string; plans: string[] }) {
  return (
    <section aria-labelledby="page-title" data-testid="draft-page">
      <PageHeading title={title} summary={summary} />
      <div className="draft-note">
        <span className="badge">Being written</span>
        <h3>Planned for this page</h3>
        <ul className="plans">
          {plans.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function MissingCharacterPage({ id }: { id: number }) {
  return (
    <section aria-labelledby="page-title" data-testid="missing-page">
      <PageHeading title="This page is missing" />
      <Link to={characterPath(id)} className="btn ghost small">
        Go to the character sheet
      </Link>
    </section>
  );
}
