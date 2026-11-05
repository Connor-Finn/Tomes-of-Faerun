import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import {
  PLAYER_PARTIES_PATH,
  dmCampaignPath,
  instanceLine,
  longDate,
  type Campaign,
  type InstanceDetail,
  type InstanceNote,
  type InstanceSummary,
} from "../../lib/campaigns";
import { BUILD_MODE_LABELS, characterPath, describe, type Build, type CharacterSummary } from "../../lib/characters";
import { SlotView } from "../characters/builderParts";
import { useFlash } from "../../lib/flash";
import { ConfirmDialog } from "../bestiary/ConfirmDialog";
import { BackupPanel, RoadmapPanel } from "./InstanceRoadmap";
import { FeaturesPage, InventoryPage, PageHeading, SheetPage, ShowPageHeading, SpellbookPage } from "../characters/CharacterTome";

const TABS = [
  { key: "sheet", label: "Sheet" },
  { key: "spellbook", label: "Spellbook" },
  { key: "inventory", label: "Inventory" },
  { key: "features", label: "Features" },
] as const;
type Tab = (typeof TABS)[number]["key"];

/**
 * A character as it stands in one campaign: hit points, the DM's notes and the full sheet.
 * The DM reads it (and manages it from the control panel); the player also gets hit point and
 * level-up controls, and can use up items, attune, and change prepared spells.
 */
export function InstanceView({
  url,
  back,
  dm = false,
  controls,
  onLoaded,
  playerUrl,
}: {
  url: string;
  back?: ReactNode;
  dm?: boolean;
  controls?: (detail: InstanceDetail, replace: (d: InstanceDetail) => void) => ReactNode;
  onLoaded?: (d: InstanceDetail | null) => void;
  /** The player's own character: where to send their changes (items used, prepared spells...). */
  playerUrl?: string;
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
        <p className="row wrap">
          <Link to={dmCampaignPath(i.campaign.id, `control/${i.id}`)} className="btn primary small">
            Manage in the control panel
          </Link>
          <span className="hint">Set their level or XP, hand out items and spells, and send notes.</span>
        </p>
      ) : (
        i.notes.length > 0 && <NoteList notes={i.notes} heading="Notes from your Dungeon Master" />
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
          {tab === "spellbook" && (
            <>
              {playerUrl && <SpellControls url={playerUrl} detail={detail} onChange={setDetail} />}
              <SpellbookPage sheet={detail.sheet} />
            </>
          )}
          {tab === "inventory" && (
            <>
              <InventoryPage
                sheet={detail.sheet}
                actions={playerUrl ? (item) => <ItemActions url={playerUrl} detail={detail} item={item} onChange={setDetail} /> : undefined}
              />
              {playerUrl && <UsedItems url={playerUrl} detail={detail} onChange={setDetail} />}
            </>
          )}
          {tab === "features" && <FeaturesPage sheet={detail.sheet} />}
        </ShowPageHeading.Provider>
      </div>
    </section>
  );
}

/** The DM's notes on a character, newest first. */
export function NoteList({
  notes,
  heading,
  onDelete,
}: {
  notes: InstanceNote[];
  heading: string;
  onDelete?: (n: InstanceNote) => void;
}) {
  return (
    <aside className="dm-note" data-testid="dm-notes" aria-label={heading}>
      <p className="dm-note-heading">{heading}</p>
      <ol className="note-list">
        {notes.map((n) => (
          <li key={n.id} data-testid="dm-note">
            <p className="note-date small muted">{longDate(n.sent_at)}</p>
            <p>{n.body}</p>
            {onDelete && (
              <button type="button" className="btn ghost small" aria-label="Delete this note" onClick={() => onDelete(n)}>
                Delete
              </button>
            )}
          </li>
        ))}
      </ol>
    </aside>
  );
}

// ================================================================ Player: items and spells in play
/** Send a change to the player's own campaign character. Earlier picks are locked on the server. */
async function patchBuild(url: string, detail: InstanceDetail, patch: Partial<Build>) {
  return api.patch<InstanceDetail>(url, { build: { ...detail.instance.build, ...patch } });
}

function ItemActions({
  url,
  detail,
  item,
  onChange,
}: {
  url: string;
  detail: InstanceDetail;
  item: InstanceDetail["sheet"]["inventory"][number];
  onChange: (d: InstanceDetail) => void;
}) {
  const { flash } = useFlash();
  const build = detail.instance.build;
  const attuned = build.attuned ?? [];

  async function send(patch: Partial<Build>, message: string) {
    const res = await patchBuild(url, detail, patch);
    if (!res.ok) {
      flash("error", res.data.error ?? "That didn't work.");
      return;
    }
    onChange(res.data);
    flash("success", message);
  }

  return (
    <span className="row wrap tight">
      <button
        type="button"
        className="btn ghost small"
        aria-label={`Use up or drop one ${item.name}`}
        onClick={() =>
          void send(
            { used: { ...(build.used ?? {}), [item.index]: (build.used?.[item.index] ?? 0) + 1 } },
            `One ${item.name} was used up.`,
          )
        }
      >
        Use one
      </button>
      {item.category === "Armor" && (
        <button
          type="button"
          className="btn ghost small"
          aria-pressed={item.equipped}
          aria-label={`${item.equipped ? "Take off" : "Wear"} ${item.name}`}
          onClick={() => {
            const slot = item.index === "shield" ? "shield" : "armor";
            const equipped = { armor: detail.sheet.equipped.armor, shield: detail.sheet.equipped.shield };
            void send(
              { equipped: { ...equipped, [slot]: item.equipped ? null : item.index } },
              item.equipped ? `${item.name} taken off.` : `Wearing ${item.name}.`,
            );
          }}
        >
          {item.equipped ? "Take off" : "Wear"}
        </button>
      )}
      {item.attunement && (
        <button
          type="button"
          className="btn ghost small"
          aria-pressed={item.attuned}
          aria-label={`${item.attuned ? "End attunement to" : "Attune to"} ${item.name}`}
          onClick={() =>
            void send(
              { attuned: item.attuned ? attuned.filter((a) => a !== item.index) : [...attuned, item.index] },
              item.attuned ? `No longer attuned to ${item.name}.` : `Attuned to ${item.name}.`,
            )
          }
        >
          {item.attuned ? "End attunement" : "Attune"}
        </button>
      )}
    </span>
  );
}

function UsedItems({ url, detail, onChange }: { url: string; detail: InstanceDetail; onChange: (d: InstanceDetail) => void }) {
  const { flash } = useFlash();
  const used = detail.sheet.used_items;
  if (used.length === 0) return null;
  const build = detail.instance.build;

  async function undo(index: string, name: string) {
    const next = { ...(build.used ?? {}) };
    next[index] = (next[index] ?? 1) - 1;
    if (next[index] <= 0) delete next[index];
    const res = await patchBuild(url, detail, { used: next });
    if (!res.ok) {
      flash("error", res.data.error ?? "That didn't work.");
      return;
    }
    onChange(res.data);
    flash("info", `One ${name} is back in the pack.`);
  }

  return (
    <section className="used-items" aria-labelledby="used-heading" data-testid="used-items">
      <h3 id="used-heading" className="leaf-heading">
        Used up or dropped
      </h3>
      <ul className="plain-list">
        {used.map((u) => (
          <li key={u.index} className="row wrap tight">
            <span>
              {u.quantity} × {u.name}
            </span>
            <button type="button" className="btn ghost small" aria-label={`Put one ${u.name} back`} onClick={() => void undo(u.index, u.name)}>
              Undo one
            </button>
          </li>
        ))}
      </ul>
      <p className="hint">Only your Dungeon Master hands out new items in a campaign.</p>
    </section>
  );
}

function SpellControls({ url, detail, onChange }: { url: string; detail: InstanceDetail; onChange: (d: InstanceDetail) => void }) {
  const { flash } = useFlash();
  const prepared = detail.slots.find((s) => s.id === "spells:prepared");
  const [editing, setEditing] = useState(false);
  const [picks, setPicks] = useState<string[]>(detail.instance.build.choices?.["spells:prepared"] ?? []);
  const wizard = detail.instance.build.class === "wizard";
  const toCopy = wizard ? detail.instance.progress.granted_spells.filter((s) => !s.copied) : [];

  async function savePrepared() {
    const build = detail.instance.build;
    const res = await patchBuild(url, detail, { choices: { ...(build.choices ?? {}), "spells:prepared": picks } });
    if (!res.ok) {
      const errors = (res.data as unknown as { errors?: { message: string }[] }).errors;
      flash("error", Array.isArray(errors) && errors[0] ? errors[0].message : res.data.error ?? "Prepared spells weren't saved.");
      return;
    }
    onChange(res.data);
    setEditing(false);
    flash("success", "Prepared spells changed.");
  }

  async function copy(index: string) {
    const res = await api.post<InstanceDetail & { message: string }>(url.replace(/\/instance$/, "/instance/spellbook"), { spell: index });
    if (!res.ok) {
      flash("error", res.data.error ?? res.data.errors?.spell ?? "The spell wasn't copied.");
      return;
    }
    onChange(res.data);
    flash("success", res.data.message);
  }

  if (!prepared && toCopy.length === 0) return null;
  return (
    <div className="spell-controls" data-testid="spell-controls">
      {toCopy.length > 0 && (
        <div className="callout" data-testid="spells-to-copy">
          <p>Your Dungeon Master gave you spells to copy into your spellbook:</p>
          <ul className="plain-list">
            {toCopy.map((s) => (
              <li key={s.index} className="row wrap tight">
                <span>
                  {s.name} <span className="muted small">(level {s.level})</span>
                </span>
                <button type="button" className="btn primary small" onClick={() => void copy(s.index)}>
                  Copy into spellbook
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {prepared && !editing && (
        <button
          type="button"
          className="btn ghost small"
          onClick={() => {
            setPicks(detail.instance.build.choices?.["spells:prepared"] ?? []);
            setEditing(true);
          }}
        >
          Change prepared spells
        </button>
      )}
      {prepared && editing && (
        <div className="prepared-editor" data-testid="prepared-editor">
          <SlotView slot={{ ...prepared, selected: picks }} mode={detail.instance.build_mode} selected={picks} onChange={setPicks} />
          <div className="row end">
            <button type="button" className="btn ghost small" onClick={() => setEditing(false)}>
              Cancel
            </button>
            <button type="button" className="btn primary small" onClick={() => void savePrepared()}>
              Save prepared spells
            </button>
          </div>
        </div>
      )}
    </div>
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
      playerUrl={url}
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
      <LevelControls campaign={campaign} detail={detail} onChange={onChange} />
      <div className="row wrap">
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
      <RoadmapPanel campaign={campaign} detail={detail} onChange={onChange} />
      <BackupPanel campaign={campaign} detail={detail} onChange={onChange} />
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
            Everything {i.name} gained in this campaign (levels, hit points, items) is lost, and so is the backup copy. Your character in the
            Character Manager is unchanged, and you can bring a character again. To leave the whole party, use the{" "}
            <Link to={PLAYER_PARTIES_PATH}>Parties</Link> page.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}

/** Level Up (Manual campaigns) or the XP counter (XP campaigns). */
function LevelControls({
  campaign,
  detail,
  onChange,
}: {
  campaign: Campaign;
  detail: InstanceDetail;
  onChange: (d: InstanceDetail) => void;
}) {
  const { flash } = useFlash();
  const navigate = useNavigate();
  const i = detail.instance;
  const p = i.progress;
  const xpMode = i.rules.levelling === "xp";
  const [gained, setGained] = useState("");
  const [error, setError] = useState<string | null>(null);
  const levelUpPath = `/play/campaigns/c/${campaign.id}/character/level-up`;

  async function addXp(e: FormEvent) {
    e.preventDefault();
    const res = await api.post<InstanceDetail & { message: string }>(`/api/campaigns/${campaign.id}/instance/xp`, {
      gained: Number(gained),
    });
    if (!res.ok) {
      setError(res.data.errors?.gained ?? res.data.error ?? "The XP wasn't added.");
      return;
    }
    setError(null);
    setGained("");
    onChange(res.data);
    // Crossing a threshold opens the level-up straight away
    if (res.data.instance.progress.levels_owed > p.levels_owed) {
      flash("success", res.data.message, { afterNavigate: true });
      navigate(levelUpPath);
    } else {
      flash("success", res.data.message);
    }
  }

  return (
    <section className="level-controls" aria-labelledby="levelling-heading" data-testid="level-controls">
      <h3 id="levelling-heading" className="leaf-heading">
        Levelling: {i.rules.levelling_label.toLowerCase()}
      </h3>
      {xpMode && (
        <>
          <p data-testid="xp-total">
            <strong>{p.xp.toLocaleString()} XP</strong>
            {p.next_level_xp !== null && <span className="muted"> · level {i.level + 1} at {p.next_level_xp.toLocaleString()} XP</span>}
          </p>
          {p.next_level_xp !== null && (
            <div className="xp-bar" aria-hidden="true">
              <div
                className="xp-fill"
                style={{
                  width: `${Math.min(100, Math.round(((p.xp - p.this_level_xp) / (p.next_level_xp - p.this_level_xp)) * 100))}%`,
                }}
              />
            </div>
          )}
          <form className="row wrap" onSubmit={addXp} aria-label="Add experience points">
            <label className="compact">
              <span>XP gained</span>
              <input type="number" min={1} value={gained} onChange={(e) => setGained(e.target.value)} aria-invalid={error ? true : undefined} />
            </label>
            <button type="submit" className="btn ghost small" disabled={!gained}>
              Add XP
            </button>
          </form>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
        </>
      )}
      {p.levels_owed > 0 && (
        <p className="notice" data-testid="levels-owed">
          {p.levels_owed === 1 ? `Level ${i.level + 1} is ready.` : `${p.levels_owed} level-ups are ready, one at a time.`}
        </p>
      )}
      {p.can_level_up ? (
        <Link to={levelUpPath} className="btn primary small">
          Level up to {i.level + 1}
        </Link>
      ) : (
        p.level_up_blocked && (
          <p className="hint" data-testid="level-up-blocked">
            {p.level_up_blocked}
          </p>
        )
      )}
      <p className="hint">
        Earlier picks are locked in a campaign. Level Up asks only for the new level's choices; hit points come{" "}
        {i.rules.hp_methods.map((m) => (m === "max" ? "the maximum" : m === "roll" ? "a roll" : "the average")).join(" or ")}.
      </p>
    </section>
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

