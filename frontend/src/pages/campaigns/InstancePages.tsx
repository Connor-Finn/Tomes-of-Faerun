import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { PLAYER_PARTIES_PATH, instanceLine, type Campaign, type InstanceDetail, type InstanceSummary } from "../../lib/campaigns";
import { BUILD_MODE_LABELS, characterPath, describe, type CharacterSummary } from "../../lib/characters";
import { useFlash } from "../../lib/flash";
import { ConfirmDialog } from "../bestiary/ConfirmDialog";
import { FeaturesPage, InventoryPage, PageHeading, SheetPage, ShowPageHeading, SpellbookPage } from "../characters/CharacterTome";

const TABS = [
  { key: "sheet", label: "Sheet" },
  { key: "spellbook", label: "Spellbook" },
  { key: "inventory", label: "Inventory" },
  { key: "features", label: "Features" },
] as const;
type Tab = (typeof TABS)[number]["key"];

/**
 * A character as it stands in one campaign: hit points, the DM's note and the full sheet.
 * The DM reads it (and writes the note); the player also gets hit point and level-up controls.
 */
export function InstanceView({
  url,
  back,
  dm = false,
  controls,
  onLoaded,
}: {
  url: string;
  back?: ReactNode;
  dm?: boolean;
  controls?: (detail: InstanceDetail, replace: (d: InstanceDetail) => void) => ReactNode;
  onLoaded?: (d: InstanceDetail | null) => void;
}) {
  const [detail, setDetail] = useState<InstanceDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [tab, setTab] = useState<Tab>("sheet");

  useEffect(() => {
    void api.get<InstanceDetail>(url).then((res) => {
      if (res.ok) setDetail(res.data);
      else setMissing(true);
      onLoaded?.(res.ok ? res.data : null);
    });
    // onLoaded is a callback from the parent; reloading only when the URL changes is intended.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  if (missing) {
    return (
      <section aria-labelledby="page-title" data-testid="instance-missing">
        {back}
        <PageHeading title="Character not found" summary="They may have left the campaign." />
      </section>
    );
  }
  if (!detail) return <p className="muted">Fetching the character sheet…</p>;
  const i = detail.instance;

  return (
    <section aria-labelledby="page-title" data-testid="instance">
      {back}
      <PageHeading title={i.name} summary={`${instanceLine(i)} · played by ${i.player.name}`} />
      <div className="instance-panel">
        <HpBar instance={i} />
        {controls?.(detail, setDetail)}
      </div>
      {dm ? (
        <DmNoteForm detail={detail} onSaved={setDetail} />
      ) : (
        i.dm_note && (
          <aside className="dm-note" data-testid="dm-note" aria-label="Note from your Dungeon Master">
            <p className="dm-note-heading">A note from your Dungeon Master</p>
            <p>{i.dm_note}</p>
          </aside>
        )
      )}

      <div className="builder-tabs instance-tabs" role="tablist" aria-label="Character pages">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            id={`instance-tab-${t.key}`}
            aria-selected={tab === t.key}
            aria-controls="instance-panel"
            className={`builder-tab${tab === t.key ? " current" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div id="instance-panel" role="tabpanel" aria-labelledby={`instance-tab-${tab}`} className="instance-sheet">
        <ShowPageHeading.Provider value={false}>
          {tab === "sheet" && <SheetPage sheet={detail.sheet} />}
          {tab === "spellbook" && <SpellbookPage sheet={detail.sheet} />}
          {tab === "inventory" && <InventoryPage sheet={detail.sheet} />}
          {tab === "features" && <FeaturesPage sheet={detail.sheet} />}
        </ShowPageHeading.Provider>
      </div>
    </section>
  );
}

function DmNoteForm({ detail, onSaved }: { detail: InstanceDetail; onSaved: (d: InstanceDetail) => void }) {
  const { flash } = useFlash();
  const i = detail.instance;
  const [note, setNote] = useState(i.dm_note);
  const dirty = note !== i.dm_note;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.put<InstanceDetail & { message: string }>(
      `/api/campaigns/${i.campaign.id}/instances/${i.id}/note`,
      { note },
    );
    if (!res.ok) {
      flash("error", res.data.errors?.note ?? res.data.error ?? "The note wasn't saved.");
      return;
    }
    onSaved(res.data);
    flash("success", res.data.message);
  }

  return (
    <form className="notes-form" onSubmit={onSubmit} aria-label="Your note on this character">
      <h3 className="leaf-heading">
        <label htmlFor="instance-note">Your note to {i.player.name}</label>
      </h3>
      <p className="hint">The player sees this on their character in this campaign. You can read the sheet, but not change it.</p>
      <textarea
        id="instance-note"
        rows={3}
        maxLength={2000}
        value={note}
        placeholder="A curse they're under, a debt they owe, a reward that's coming…"
        onChange={(e) => setNote(e.target.value)}
      />
      <div className="row end">
        <button type="submit" className="btn primary small" disabled={!dirty}>
          Save note
        </button>
      </div>
    </form>
  );
}

// ================================================================ Player: Your character
/** Player Mode › a campaign › Your character: bring one, then play it. */
export function PlayerCharacterPage({ campaign, onChange }: { campaign: Campaign; onChange: () => Promise<void> }) {
  const url = `/api/campaigns/${campaign.id}/instance`;
  if (!campaign.my_instance) return <BringCharacter campaign={campaign} onJoined={onChange} />;
  return (
    <InstanceView
      url={url}
      controls={(detail, replace) => <PlayerControls campaign={campaign} detail={detail} onChange={replace} onLeft={onChange} />}
    />
  );
}

function BringCharacter({ campaign, onJoined }: { campaign: Campaign; onJoined: () => Promise<void> }) {
  const { flash } = useFlash();
  const [characters, setCharacters] = useState<CharacterSummary[] | null>(null);
  const [choice, setChoice] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.get<{ characters: CharacterSummary[] }>("/api/characters").then((res) => res.ok && setCharacters(res.data.characters));
  }, []);

  const ready = (characters ?? []).filter((c) => c.status === "complete");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.post<InstanceDetail & { message: string }>(`/api/campaigns/${campaign.id}/instance`, {
      character_id: Number(choice),
    });
    if (!res.ok) {
      setError(res.data.errors?.character_id ?? res.data.error ?? "Your character couldn't join.");
      return;
    }
    flash("success", res.data.message);
    await onJoined();
  }

  return (
    <section aria-labelledby="page-title" data-testid="bring-character">
      <PageHeading
        title="Your character"
        summary="Choose who you'll play. They join as a copy: levels, hit points and items gained here stay in this campaign, and your character in the Character Manager doesn't change."
      />
      {characters && ready.length === 0 ? (
        <div className="empty-page" data-testid="no-ready-characters">
          <p>You need a finished character first.</p>
          <Link to="/play/characters/create" className="btn ghost">
            Create a character
          </Link>
        </div>
      ) : (
        <form className="character-choices" onSubmit={onSubmit} aria-label="Choose your character">
          <fieldset>
            <legend className="sr-only">Your finished characters</legend>
            <ul className="character-list">
              {ready.map((c) => (
                <li key={c.id} className={`character-card choosable${choice === String(c.id) ? " chosen" : ""}`}>
                  <label className="check">
                    <input
                      type="radio"
                      name="character"
                      value={c.id}
                      checked={choice === String(c.id)}
                      onChange={(e) => {
                        setChoice(e.target.value);
                        setError(null);
                      }}
                    />
                    <span>
                      <strong className="character-name">{c.name}</strong>
                      <span className="character-line">{describe(c)}</span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
          {error && (
            <p className="form-error-summary" role="alert">
              {error}
            </p>
          )}
          <div className="row end">
            <button type="submit" className="btn primary" disabled={!choice}>
              Bring this character
            </button>
          </div>
          {characters && characters.length > ready.length && (
            <p className="hint">Drafts aren't listed. Finish them in the Character Manager to bring them along.</p>
          )}
        </form>
      )}
    </section>
  );
}

function PlayerControls({
  campaign,
  detail,
  onChange,
  onLeft,
}: {
  campaign: Campaign;
  detail: InstanceDetail;
  onChange: (d: InstanceDetail) => void;
  onLeft: () => Promise<void>;
}) {
  const { flash } = useFlash();
  const i = detail.instance;
  const [hp, setHp] = useState(String(i.current_hp));
  const [temp, setTemp] = useState(String(i.temp_hp));
  const [leaving, setLeaving] = useState(false);
  const url = `/api/campaigns/${campaign.id}/instance`;
  useEffect(() => {
    setHp(String(i.current_hp));
    setTemp(String(i.temp_hp));
  }, [i.current_hp, i.temp_hp]);

  const save = useCallback(
    async (body: { current_hp?: number; temp_hp?: number }, message?: string) => {
      const res = await api.patch<InstanceDetail>(url, body);
      if (!res.ok) {
        flash("error", res.data.error ?? "Hit points weren't saved.");
        setHp(String(i.current_hp));
        setTemp(String(i.temp_hp));
        return;
      }
      onChange(res.data);
      if (message) flash("success", message);
    },
    [url, i.current_hp, i.temp_hp, onChange, flash],
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void save({ current_hp: Number(hp), temp_hp: Number(temp) }, "Hit points updated.");
  }

  return (
    <div className="player-controls">
      <form className="row wrap hp-form" onSubmit={onSubmit} aria-label="Hit points">
        <label className="compact">
          <span>Current HP</span>
          <input type="number" min={0} max={i.max_hp} value={hp} onChange={(e) => setHp(e.target.value)} />
        </label>
        <label className="compact">
          <span>Temporary HP</span>
          <input type="number" min={0} max={999} value={temp} onChange={(e) => setTemp(e.target.value)} />
        </label>
        <button type="submit" className="btn primary small">
          Update HP
        </button>
        <button
          type="button"
          className="btn ghost small"
          onClick={() => void save({ current_hp: i.max_hp, temp_hp: 0 }, `${i.name} took a long rest.`)}
        >
          Long rest
        </button>
      </form>
      <div className="row wrap">
        <Link to={`/play/campaigns/c/${campaign.id}/character/edit`} className="btn primary small">
          Level up or change
        </Link>
        <button type="button" className="btn ghost small" onClick={() => setLeaving(true)}>
          Leave with this character
        </button>
      </div>
      <p className="hint" data-testid="instance-origin">
        {BUILD_MODE_LABELS[i.build_mode]} ·{" "}
        {i.base_character ? (
          <>
            copied from <Link to={characterPath(i.base_character.id)}>{i.base_character.name}</Link> in the Character
            Manager, which stays at level {i.base_character.level}
          </>
        ) : (
          "the original character was deleted from the Character Manager; this copy carries on"
        )}
        .
      </p>
      {leaving && (
        <ConfirmDialog
          title={`Take ${i.name} out of ${campaign.name}?`}
          confirmLabel="Leave"
          onClose={() => setLeaving(false)}
          onConfirm={async () => {
            const res = await api.delete<{ message: string }>(url);
            if (!res.ok) return res.data.error ?? "Your character didn't leave.";
            flash("info", res.data.message);
            await onLeft();
          }}
        >
          <p>
            Everything {i.name} gained in this campaign (levels, hit points, items) is lost. Your character in the
            Character Manager is unchanged, and you can bring a character again. To leave the whole party, use the{" "}
            <Link to={PLAYER_PARTIES_PATH}>Parties</Link> page.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}

export function HpBar({ instance }: { instance: Pick<InstanceSummary, "current_hp" | "max_hp" | "temp_hp"> }) {
  const pct = instance.max_hp ? Math.round((instance.current_hp / instance.max_hp) * 100) : 0;
  return (
    <div className="hp-bar" data-testid="hp-bar">
      <div
        className={`hp-fill${pct <= 25 ? " low" : pct <= 50 ? " mid" : ""}`}
        style={{ width: `${pct}%` }}
        aria-hidden="true"
      />
      <span className="hp-text">
        {instance.current_hp}/{instance.max_hp} HP{instance.temp_hp > 0 && ` + ${instance.temp_hp} temp`}
      </span>
    </div>
  );
}

