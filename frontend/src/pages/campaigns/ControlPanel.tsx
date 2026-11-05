import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import {
  HP_METHOD_LABELS,
  dmCampaignPath,
  instanceLine,
  type Campaign,
  type InstanceDetail,
  type InstanceSummary,
  type Levelling,
} from "../../lib/campaigns";
import type { HpMethod } from "../../lib/characters";
import type { ItemResults, ItemSummary } from "../../lib/items";
import type { SpellResults, SpellSummary } from "../../lib/spells";
import { useFlash } from "../../lib/flash";
import { PageHeading } from "../characters/CharacterTome";
import { HpBar, NoteList } from "./InstancePages";

/**
 * The Dungeon Master's control panel (agreed with Connor, 2026-11-04).
 *
 * The DM sets the campaign's rules (how characters level and gain hit points) and, for each player,
 * can set their level or XP, hand out and take away items, grant spells and send notes. The DM never
 * changes a player's own picks: only the player does, through Level Up.
 */
const HP_METHODS: HpMethod[] = ["average", "roll", "max"];
const HP_HINTS: Record<HpMethod, string> = {
  average: "The hit die's average, rounded up: steady and fair.",
  roll: "The app rolls the hit die once. No rerolls.",
  max: "The hit die's highest number: tougher heroes.",
};

type Detail = InstanceDetail & { message?: string };

export function DmControlPanel({ campaign, onChange }: { campaign: Campaign; onChange: (c: Campaign) => void }) {
  const { flash } = useFlash();
  const [levelling, setLevelling] = useState<Levelling>(campaign.rules.levelling);
  const [methods, setMethods] = useState<HpMethod[]>(campaign.rules.hp_methods);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const dirty =
    levelling !== campaign.rules.levelling ||
    methods.length !== campaign.rules.hp_methods.length ||
    methods.some((m) => !campaign.rules.hp_methods.includes(m));

  async function saveRules(e: FormEvent) {
    e.preventDefault();
    const res = await api.put<{ campaign: Campaign; message: string }>(`/api/campaigns/${campaign.id}/rules`, {
      levelling,
      hp_methods: methods,
    });
    if (!res.ok) {
      setErrors(res.data.errors ?? { levelling: res.data.error ?? "The rules weren't saved." });
      return;
    }
    setErrors({});
    onChange(res.data.campaign);
    flash("success", res.data.message);
  }

  const players = campaign.players.filter((p) => p.instance);
  return (
    <section aria-labelledby="page-title" data-testid="control-panel">
      <PageHeading
        title="Control panel"
        summary="Set how characters level up, then look after each player: their level or XP, items, spells and notes. Players still make their own picks."
      />
      <form className="notes-form rules-form" onSubmit={saveRules} aria-label="Campaign rules">
        <h3 className="leaf-heading">Campaign rules</h3>
        <fieldset className="field">
          <legend>How do characters level up?</legend>
          <div className="choice-grid two">
            <label className={`choice-card${levelling === "manual" ? " on" : ""}`}>
              <input type="radio" name="levelling" value="manual" checked={levelling === "manual"} onChange={() => setLevelling("manual")} />
              <strong>Manual</strong>
              <span className="small">Players press Level Up themselves when the table agrees. No XP to track.</span>
            </label>
            <label className={`choice-card${levelling === "xp" ? " on" : ""}`}>
              <input type="radio" name="levelling" value="xp" checked={levelling === "xp"} onChange={() => setLevelling("xp")} />
              <strong>Experience points</strong>
              <span className="small">Players add the XP they earn. Crossing a threshold opens Level Up.</span>
            </label>
          </div>
          {errors.levelling && <p className="field-error">{errors.levelling}</p>}
        </fieldset>
        <fieldset className="field">
          <legend>How may players gain hit points when they level up?</legend>
          <div className="row wrap">
            {HP_METHODS.map((m) => (
              <label key={m} className="check" title={HP_HINTS[m]}>
                <input
                  type="checkbox"
                  name="hp-methods"
                  value={m}
                  checked={methods.includes(m)}
                  onChange={(e) => setMethods(e.target.checked ? [...methods, m] : methods.filter((x) => x !== m))}
                />
                {HP_METHOD_LABELS[m]}
              </label>
            ))}
          </div>
          <p className="hint">Average: {HP_HINTS.average} Roll: {HP_HINTS.roll} Maximum: {HP_HINTS.max}</p>
          {errors.hp_methods && (
            <p className="field-error" data-testid="error-hp_methods">
              {errors.hp_methods}
            </p>
          )}
        </fieldset>
        <div className="row end">
          <button type="submit" className="btn primary small" disabled={!dirty}>
            Save rules
          </button>
        </div>
      </form>

      <h3 className="leaf-heading">Players</h3>
      {players.length === 0 ? (
        <p className="muted" data-testid="no-player-characters">
          No one has brought a character yet.
        </p>
      ) : (
        <ul className="player-list" data-testid="control-players">
          {players.map((p) => {
            const inst = p.instance as InstanceSummary;
            return (
              <li key={p.id} className="player-card" data-testid="control-player">
                <p className="player-name">{p.name}</p>
                <p>
                  <strong className="character-name">{inst.name}</strong> <span className="muted small">{instanceLine(inst)}</span>
                </p>
                <HpBar instance={inst} />
                <p className="small">
                  {campaign.rules.levelling === "xp" && <>{inst.xp.toLocaleString()} XP · </>}
                  {inst.levels_owed > 0 ? `${inst.levels_owed} level-up${inst.levels_owed > 1 ? "s" : ""} waiting` : "Up to date"}
                </p>
                <Link to={dmCampaignPath(campaign.id, `control/${inst.id}`)} className="btn ghost small" aria-label={`Manage ${inst.name}`}>
                  Manage
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** One player's character in the control panel. */
export function DmPlayerControl({ campaign, instanceId }: { campaign: Campaign; instanceId: number }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [missing, setMissing] = useState(false);
  const url = `/api/campaigns/${campaign.id}/instances/${instanceId}`;

  useEffect(() => {
    void api.get<Detail>(url).then((res) => (res.ok ? setDetail(res.data) : setMissing(true)));
  }, [url]);

  const back = (
    <Link to={dmCampaignPath(campaign.id, "control")} className="back-link">
      ← Back to the control panel
    </Link>
  );
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
  const props = { url, detail, onChange: setDetail };

  return (
    <section aria-labelledby="page-title" data-testid="player-control">
      {back}
      <PageHeading title={i.name} summary={`${instanceLine(i)} · played by ${i.player.name}`} />
      <div className="row wrap">
        <HpBar instance={i} />
        <Link to={dmCampaignPath(campaign.id, `party/${i.id}`)} className="btn ghost small">
          Read the full sheet
        </Link>
      </div>
      <LevelPanel {...props} />
      <ItemsPanel {...props} />
      <SpellsPanel {...props} />
      <NotesPanel {...props} />
    </section>
  );
}

interface PanelProps {
  url: string;
  detail: Detail;
  onChange: (d: Detail) => void;
}

function useSend(onChange: (d: Detail) => void) {
  const { flash } = useFlash();
  return async (call: Promise<{ ok: boolean; data: Detail & { error?: string; errors?: Record<string, string> } }>) => {
    const res = await call;
    if (!res.ok) {
      const first = res.data.errors ? Object.values(res.data.errors)[0] : null;
      flash("error", first ?? res.data.error ?? "That didn't work.");
      return false;
    }
    onChange(res.data);
    if (res.data.message) flash("success", res.data.message);
    return true;
  };
}

// ---------------------------------------------------------------- level and XP
function LevelPanel({ url, detail, onChange }: PanelProps) {
  const send = useSend(onChange);
  const i = detail.instance;
  const p = i.progress;
  const [level, setLevel] = useState(String(i.level));
  const [xp, setXp] = useState(String(p.xp));
  useEffect(() => {
    setLevel(String(i.level));
    setXp(String(i.progress.xp));
  }, [i.level, i.progress.xp]);

  return (
    <section className="control-section" aria-labelledby="level-heading" data-testid="level-panel">
      <h3 id="level-heading" className="leaf-heading">
        Level{i.rules.levelling === "xp" ? " and XP" : ""}
      </h3>
      <p className="small">
        Level {i.level}
        {i.rules.levelling === "xp" && ` · ${p.xp.toLocaleString()} XP`}
        {p.levels_owed > 0 && ` · ${p.levels_owed} level-up${p.levels_owed > 1 ? "s" : ""} waiting for ${i.player.name}`}
      </p>
      <div className="row wrap">
        <form
          className="row wrap tight"
          aria-label="Set level"
          onSubmit={(e) => {
            e.preventDefault();
            void send(api.put<Detail>(`${url}/progress`, { level: Number(level) }));
          }}
        >
          <label className="compact">
            <span>Level</span>
            <input type="number" min={p.lowest_level} max={20} value={level} onChange={(e) => setLevel(e.target.value)} />
          </label>
          <button type="submit" className="btn ghost small" disabled={Number(level) === i.level && !p.target_level}>
            Set level
          </button>
        </form>
        {i.rules.levelling === "xp" && (
          <form
            className="row wrap tight"
            aria-label="Set XP"
            onSubmit={(e) => {
              e.preventDefault();
              void send(api.put<Detail>(`${url}/progress`, { xp: Number(xp) }));
            }}
          >
            <label className="compact">
              <span>XP</span>
              <input type="number" min={0} value={xp} onChange={(e) => setXp(e.target.value)} />
            </label>
            <button type="submit" className="btn ghost small" disabled={Number(xp) === p.xp}>
              Set XP
            </button>
          </form>
        )}
      </div>
      <p className="hint">
        Raising the level lets {i.player.name} level up, one level at a time with their own picks. Lowering it takes{" "}
        {i.name} back to how they were at that level (level {p.lowest_level} at the lowest), keeping their items.
      </p>
    </section>
  );
}

// ---------------------------------------------------------------- items
function ItemsPanel({ url, detail, onChange }: PanelProps) {
  const send = useSend(onChange);
  const i = detail.instance;
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ItemSummary[]>([]);
  const [quantity, setQuantity] = useState("1");

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const timer = window.setTimeout(() => {
      void api
        .get<ItemResults>(`/api/items?${new URLSearchParams({ q: query.trim(), per_page: "8" })}`)
        .then((res) => res.ok && setResults(res.data.results));
    }, 200);
    return () => window.clearTimeout(timer);
  }, [query]);

  return (
    <section className="control-section" aria-labelledby="items-heading" data-testid="items-panel">
      <h3 id="items-heading" className="leaf-heading">
        Items
      </h3>
      <p className="hint">Only you hand out items in a campaign. {i.player.name} can use them up or drop them.</p>
      <div className="row wrap">
        <label className="compact grow">
          <span>Give an item</span>
          <input type="search" value={query} placeholder="Search the catalogue…" onChange={(e) => setQuery(e.target.value)} />
        </label>
        <label className="compact">
          <span>How many</span>
          <input type="number" min={1} max={999} value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        </label>
      </div>
      {results.length > 0 && (
        <ul className="plain-list search-results" data-testid="item-results">
          {results.map((r) => (
            <li key={r.index} className="row wrap tight">
              <span>
                {r.name} <span className="muted small">{r.rarity ? `${r.category}, ${r.rarity.toLowerCase()}` : r.category}</span>
              </span>
              <button
                type="button"
                className="btn primary small"
                aria-label={`Give ${r.name}`}
                onClick={async () => {
                  if (await send(api.post<Detail>(`${url}/items`, { item: r.index, quantity: Number(quantity) || 1 }))) setQuery("");
                }}
              >
                Give
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="table-wrap">
        <table data-testid="dm-inventory">
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col">Qty</th>
              <th scope="col">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {detail.sheet.inventory.map((item) => (
              <tr key={item.index} data-testid="dm-inventory-item">
                <td>
                  {item.name} {item.given > 0 && <span className="pill">{item.given === item.quantity ? "From you" : `${item.given} from you`}</span>}
                </td>
                <td>{item.quantity}</td>
                <td>
                  <button
                    type="button"
                    className="btn ghost small"
                    aria-label={`Take one ${item.name}`}
                    onClick={() => void send(api.delete<Detail>(`${url}/items/${item.index}?quantity=1`))}
                  >
                    Take one
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- spells
function SpellsPanel({ url, detail, onChange }: PanelProps) {
  const send = useSend(onChange);
  const i = detail.instance;
  const wizard = i.build.class === "wizard";
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SpellSummary[]>([]);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({ q: query.trim(), per_page: "8" });
      void api.get<SpellResults>(`/api/spells?${params}`).then((res) => res.ok && setResults(res.data.results));
    }, 200);
    return () => window.clearTimeout(timer);
  }, [query]);

  const granted = i.progress.granted_spells;
  return (
    <section className="control-section" aria-labelledby="spells-heading" data-testid="spells-panel">
      <h3 id="spells-heading" className="leaf-heading">
        Spells
      </h3>
      <p className="hint">
        {wizard
          ? `${i.name} is a wizard: a spell you grant is a scroll or spellbook they find, and they copy it into their own spellbook.`
          : `A spell you grant is simply known by ${i.name}, and always prepared.`}
      </p>
      {granted.length > 0 && (
        <ul className="plain-list" data-testid="granted-spells">
          {granted.map((s) => (
            <li key={s.index} className="row wrap tight" data-testid="granted-spell">
              <span>
                {s.name} <span className="muted small">{s.level === 0 ? "cantrip" : `level ${s.level}`}</span>
                {wizard && <span className="pill">{s.copied ? "In the spellbook" : "Not copied yet"}</span>}
              </span>
              <button
                type="button"
                className="btn ghost small"
                aria-label={`Take back ${s.name}`}
                onClick={() => void send(api.delete<Detail>(`${url}/spells/${s.index}`))}
              >
                Take back
              </button>
            </li>
          ))}
        </ul>
      )}
      <label className="compact">
        <span>Grant a spell</span>
        <input type="search" value={query} placeholder="Search the spells…" onChange={(e) => setQuery(e.target.value)} />
      </label>
      {results.length > 0 && (
        <ul className="plain-list search-results" data-testid="spell-results">
          {results.map((r) => (
            <li key={r.index} className="row wrap tight">
              <span>
                {r.name} <span className="muted small">{r.level === 0 ? "cantrip" : `level ${r.level}`} · {r.school}</span>
              </span>
              <button
                type="button"
                className="btn primary small"
                aria-label={`Grant ${r.name}`}
                onClick={async () => {
                  if (await send(api.post<Detail>(`${url}/spells`, { spell: r.index }))) setQuery("");
                }}
              >
                Grant
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- notes
function NotesPanel({ url, detail, onChange }: PanelProps) {
  const send = useSend(onChange);
  const i = detail.instance;
  const [body, setBody] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (await send(api.post<Detail>(`${url}/notes`, { body }))) setBody("");
  }

  return (
    <section className="control-section" aria-labelledby="notes-heading" data-testid="notes-panel">
      <h3 id="notes-heading" className="leaf-heading">
        Notes to {i.player.name}
      </h3>
      <form className="notes-form" onSubmit={onSubmit} aria-label={`Send a note to ${i.player.name}`}>
        <label htmlFor="instance-note" className="sr-only">
          Your note
        </label>
        <textarea
          id="instance-note"
          rows={3}
          maxLength={2000}
          value={body}
          placeholder="A curse they're under, a debt they owe, a reward that's coming…"
          onChange={(e) => setBody(e.target.value)}
        />
        <div className="row end">
          <button type="submit" className="btn primary small" disabled={!body.trim()}>
            Send note
          </button>
        </div>
      </form>
      {i.notes.length > 0 ? (
        <NoteList
          notes={i.notes}
          heading={`Sent to ${i.player.name}`}
          onDelete={(n) => void send(api.delete<Detail>(`${url}/notes/${n.id}`))}
        />
      ) : (
        <p className="muted small">No notes sent yet. They build up as a list the player reads in this campaign.</p>
      )}
    </section>
  );
}
