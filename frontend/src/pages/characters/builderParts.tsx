import { useId, useState, type ReactNode } from "react";
import type { Ability, BuildMode, CharacterOptions, Sheet, Slot, SlotOption } from "../../lib/characters";
import { signed } from "../../lib/characters";
import { useFavouriteSpells } from "../../lib/spells";
import { FavouriteStar, SpellReader } from "../spells/SpellText";

/**
 * The pieces of the character builder. None of them knows a D&D rule: they show the slots the
 * server sends (options, denied reasons, help) and report the player's picks back.
 *
 * Easy build hides denied options and opens the help. Standard build shows every option and lets
 * the player try a denied one, which is then refused with the reason.
 */

// ---------------------------------------------------------------- help
export function Help({ text, mode, label = "Help" }: { text: ReactNode; mode: BuildMode; label?: string }) {
  const [open, setOpen] = useState(mode === "easy");
  const id = useId();
  if (!text) return null;
  return (
    <div className="help">
      <button
        type="button"
        className="help-toggle"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        title={open ? "Hide help" : "Show help"}
      >
        <span aria-hidden="true">?</span>
        <span className="sr-only">{label}</span>
      </button>
      {open && (
        <div id={id} className="help-text" data-testid="help-text">
          {text}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- slots
export interface SlotProps {
  slot: Slot;
  selected: string[];
  mode: BuildMode;
  onChange: (values: string[]) => void;
}

/** Status line for a slot: how many picked, or why the last attempt was refused. */
function SlotStatus({ slot, selected, notice }: { slot: Slot; selected: string[]; notice: string | null }) {
  const want = slot.exact ? `Pick ${slot.choose}` : `Pick up to ${slot.choose}`;
  return (
    <>
      <p className="slot-count" data-testid="slot-count">
        {want} · {selected.length} chosen
        {slot.complete && !slot.errors.length && <span className="slot-done"> ✓</span>}
      </p>
      {notice && (
        <p className="field-error" role="alert" data-testid="slot-denied">
          {notice}
        </p>
      )}
      {slot.errors.map((e) => (
        <p key={e} className="field-error" data-testid="slot-error">
          {e}
        </p>
      ))}
    </>
  );
}

/** Shared pick logic: toggling, the pick limit and refusing denied options. */
function usePicker({ slot, selected, onChange }: SlotProps) {
  const [notice, setNotice] = useState<string | null>(null);
  function toggle(o: SlotOption) {
    if (selected.includes(o.value)) {
      setNotice(null);
      onChange(selected.filter((v) => v !== o.value));
      return;
    }
    if (o.denied) {
      setNotice(`You can't take ${o.label}: ${o.denied}`);
      return;
    }
    if (slot.choose === 1) {
      setNotice(null);
      onChange([o.value]);
      return;
    }
    if (selected.length >= slot.choose) {
      setNotice(`You can pick ${slot.choose}. Remove one first.`);
      return;
    }
    setNotice(null);
    onChange([...selected, o.value]);
  }
  return { notice, toggle };
}

/** A readable name for a pick that isn't among the options: "skill-insight" -> "Insight". */
export function pickLabel(value: string): string {
  const words = value.replace(/^(skill|saving-throw|feat)[-:]/, "").replace(/-/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function visibleOptions(slot: Slot, selected: string[], mode: BuildMode): SlotOption[] {
  return mode === "easy" ? slot.options.filter((o) => !o.denied || selected.includes(o.value)) : slot.options;
}

/** A choice shown as a set of toggle chips (skills, languages, fighting styles, equipment...). */
export function ChipSlot(props: SlotProps) {
  const { slot, selected, mode } = props;
  const { notice, toggle } = usePicker(props);
  const options = visibleOptions(slot, selected, mode);
  // Picks saved earlier that aren't on offer any more: shown so they can be seen and removed
  const unavailable = selected.filter((v) => !slot.options.some((o) => o.value === v));
  return (
    <fieldset className="slot" data-testid="slot" data-slot={slot.id}>
      <legend>
        {slot.label}
        {slot.level > 1 && <span className="muted small"> · level {slot.level}</span>}
      </legend>
      <Help text={slot.help} mode={mode} label={`About ${slot.label}`} />
      <SlotStatus slot={slot} selected={selected} notice={notice} />
      <div className="chips">
        {options.map((o) => {
          const on = selected.includes(o.value);
          return (
            <button
              key={o.value}
              type="button"
              className={`chip${on ? " on" : ""}${o.denied ? " denied" : ""}`}
              aria-pressed={on}
              title={o.denied}
              onClick={() => toggle(o)}
            >
              {o.label}
            </button>
          );
        })}
        {unavailable.map((v) => (
          <button
            key={v}
            type="button"
            className="chip on unavailable"
            aria-pressed="true"
            title="No longer one of the options. Click to remove it."
            data-testid="unavailable-pick"
            onClick={() => toggle({ value: v, label: pickLabel(v) })}
          >
            {pickLabel(v)} ✕
          </button>
        ))}
      </div>
      {mode === "easy" && options.length < slot.options.length && (
        <p className="hint">{slot.options.length - options.length} options you can't take are hidden.</p>
      )}
    </fieldset>
  );
}

/**
 * A spell choice: the spells picked, then a searchable catalogue to add from. Each spell can be
 * read in place, and your favourite spells (starred here or in the spell tome) come first.
 */
export function SpellSlot(props: SlotProps) {
  const { slot, selected, mode } = props;
  const { notice, toggle } = usePicker(props);
  const { isFavourite, toggle: toggleFavourite } = useFavouriteSpells();
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("");
  const [onlyAllowed, setOnlyAllowed] = useState(false);
  const [onlyFavourites, setOnlyFavourites] = useState(false);
  const [reading, setReading] = useState<string | null>(null);
  const searchId = useId();
  const levelId = useId();

  const byValue = new Map(slot.options.map((o) => [o.value, o]));
  const levels = [...new Set(slot.options.map((o) => o.level ?? 0))].sort((a, b) => a - b);
  let shown = visibleOptions(slot, selected, mode).filter((o) => !selected.includes(o.value));
  if (onlyAllowed) shown = shown.filter((o) => !o.denied);
  if (onlyFavourites) shown = shown.filter((o) => isFavourite(o.value));
  if (level !== "") shown = shown.filter((o) => String(o.level ?? 0) === level);
  if (query.trim()) shown = shown.filter((o) => o.label.toLowerCase().includes(query.trim().toLowerCase()));
  shown = [...shown.filter((o) => isFavourite(o.value)), ...shown.filter((o) => !isFavourite(o.value))];

  return (
    <fieldset className="slot spell-slot" data-testid="slot" data-slot={slot.id}>
      <legend>{slot.label}</legend>
      <Help text={slot.help} mode={mode} label={`About ${slot.label}`} />
      <SlotStatus slot={slot} selected={selected} notice={notice} />
      <ul className="picked-spells" aria-label={`${slot.label} chosen`} data-testid="picked">
        {selected.length === 0 && <li className="muted small">None yet.</li>}
        {selected.map((v) => (
          <li key={v}>
            <span>{byValue.get(v)?.label ?? pickLabel(v)}</span>
            <button type="button" className="btn ghost small" onClick={() => toggle(byValue.get(v) ?? { value: v, label: pickLabel(v) })}>
              Remove<span className="sr-only"> {byValue.get(v)?.label ?? pickLabel(v)}</span>
            </button>
          </li>
        ))}
      </ul>
      <div className="catalogue-filters">
        <div className="field">
          <label htmlFor={searchId}>Search spells</label>
          <input id={searchId} type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Fire bolt…" />
        </div>
        {levels.length > 1 && (
          <div className="field">
            <label htmlFor={levelId}>Spell level</label>
            <select id={levelId} value={level} onChange={(e) => setLevel(e.target.value)}>
              <option value="">Any level</option>
              {levels.map((l) => (
                <option key={l} value={l}>
                  {l === 0 ? "Cantrip" : `Level ${l}`}
                </option>
              ))}
            </select>
          </div>
        )}
        {mode === "standard" && (
          <label className="check">
            <input type="checkbox" checked={onlyAllowed} onChange={(e) => setOnlyAllowed(e.target.checked)} />
            Only spells I can take
          </label>
        )}
        <label className="check">
          <input type="checkbox" checked={onlyFavourites} onChange={(e) => setOnlyFavourites(e.target.checked)} />
          Only my favourites
        </label>
      </div>
      <ul className="catalogue" aria-label={`${slot.label} catalogue`} data-testid="catalogue">
        {shown.slice(0, 60).map((o) => (
          <li key={o.value} className={o.denied ? "denied" : mode === "easy" ? "allowed" : undefined} data-testid="catalogue-spell">
            <FavouriteStar name={o.label} on={isFavourite(o.value)} onToggle={() => void toggleFavourite(o.value)} />
            <span className="spell-name">{o.label}</span>
            <span className="muted small">
              {o.level ? `Level ${o.level}` : "Cantrip"} · {o.school}
            </span>
            {o.denied && <span className="deny-reason small">{o.denied}</span>}
            <span className="catalogue-actions">
              <button
                type="button"
                className="btn ghost small"
                aria-expanded={reading === o.value}
                onClick={() => setReading((r) => (r === o.value ? null : o.value))}
              >
                {reading === o.value ? "Close" : "Read"}
                <span className="sr-only"> {o.label}</span>
              </button>
              <button type="button" className="btn ghost small" onClick={() => toggle(o)}>
                Add<span className="sr-only"> {o.label}</span>
              </button>
            </span>
            {reading === o.value && <SpellReader index={o.value} />}
          </li>
        ))}
        {shown.length === 0 && (
          <li className="muted">{onlyFavourites ? "None of your favourites fit here. Star spells with ☆ to keep them handy." : "No spells match."}</li>
        )}
        {shown.length > 60 && <li className="muted small">…and {shown.length - 60} more. Search to narrow the list.</li>}
      </ul>
    </fieldset>
  );
}

/** Ability Score Improvement: +2 to one score, +1 to two, or a feat. */
export function AsiSlot({ slot, selected, mode, onChange }: SlotProps) {
  const isFeat = selected.length === 1 && selected[0].startsWith("feat:");
  const [kind, setKind] = useState<"scores" | "feat">(isFeat ? "feat" : "scores");
  const abilities = visibleOptions(slot, selected, mode).filter((o) => o.kind === "ability");
  const feats = slot.options.filter((o) => o.kind === "feat" && (mode === "standard" || !o.denied || selected.includes(o.value)));
  const [notice, setNotice] = useState<string | null>(null);
  const firstId = useId();
  const secondId = useId();
  const featId = useId();
  const scores = isFeat ? [] : selected;

  function setScore(i: number, value: string) {
    const next = [...scores];
    next[i] = value;
    onChange(next.filter(Boolean));
  }
  function pickFeat(value: string) {
    const o = slot.options.find((x) => x.value === value);
    if (o?.denied) {
      setNotice(`You can't take ${o.label}: ${o.denied}`);
      return;
    }
    setNotice(null);
    onChange(value ? [value] : []);
  }

  return (
    <fieldset className="slot" data-testid="slot" data-slot={slot.id}>
      <legend>{slot.label}</legend>
      <Help text={slot.help} mode={mode} label={`About ${slot.label}`} />
      <div className="row wrap">
        <label className="check">
          <input type="radio" name={`${slot.id}-kind`} checked={kind === "scores"} onChange={() => { setKind("scores"); onChange([]); }} />
          Raise ability scores
        </label>
        <label className="check">
          <input type="radio" name={`${slot.id}-kind`} checked={kind === "feat"} onChange={() => { setKind("feat"); onChange([]); }} />
          Take a feat
        </label>
      </div>
      {kind === "scores" ? (
        <div className="row wrap">
          {[0, 1].map((i) => (
            <div className="field" key={i}>
              <label htmlFor={i === 0 ? firstId : secondId}>{i === 0 ? "First +1" : "Second +1"}</label>
              <select id={i === 0 ? firstId : secondId} value={scores[i] ?? ""} onChange={(e) => setScore(i, e.target.value)}>
                <option value="">Choose…</option>
                {abilities.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label.replace(" +1", "")}
                    {o.denied ? ` (${o.denied})` : ""}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      ) : (
        <div className="field">
          <label htmlFor={featId}>Feat</label>
          <select id={featId} value={isFeat ? selected[0] : ""} onChange={(e) => pickFeat(e.target.value)}>
            <option value="">Choose…</option>
            {feats.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label.replace("Feat: ", "")}
                {o.denied ? ` (${o.denied})` : ""}
              </option>
            ))}
          </select>
        </div>
      )}
      {notice && (
        <p className="field-error" role="alert" data-testid="slot-denied">
          {notice}
        </p>
      )}
      {slot.errors.map((e) => (
        <p key={e} className="field-error" data-testid="slot-error">
          {e}
        </p>
      ))}
    </fieldset>
  );
}

export function SlotView(props: SlotProps) {
  if (props.slot.kind === "asi") return <AsiSlot {...props} />;
  if (props.slot.kind === "spell" && props.slot.options.length > 30) return <SpellSlot {...props} />;
  return <ChipSlot {...props} />;
}

// ---------------------------------------------------------------- ability scores
export interface AbilityScoresValue {
  method?: string;
  base?: Partial<Record<Ability, number>>;
}

export function AbilityScores({
  value,
  options,
  sheet,
  mode,
  onChange,
}: {
  value: AbilityScoresValue;
  options: CharacterOptions;
  sheet: Sheet;
  mode: BuildMode;
  onChange: (v: AbilityScoresValue) => void;
}) {
  const method = value.method ?? "";
  const base = value.base ?? {};
  const spent = Object.values(base).reduce((sum, v) => sum + (options.point_buy.costs[String(v)] ?? 0), 0);
  const left = options.point_buy.budget - spent;
  const used = Object.values(base);

  function setMethod(m: string) {
    if (m === "point-buy") onChange({ method: m, base: Object.fromEntries(options.abilities.map((a) => [a.key, 8])) });
    else onChange({ method: m, base: {} });
  }
  function setScore(key: Ability, v: number | undefined) {
    const next = { ...base };
    if (v === undefined) delete next[key];
    else next[key] = v;
    onChange({ method, base: next });
  }

  return (
    <div className="ability-builder">
      <fieldset className="field">
        <legend>How do you want to set your scores?</legend>
        <div className="row wrap">
          {options.ability_methods.map((m) => (
            <label key={m.value} className="check">
              <input type="radio" name="ability-method" value={m.value} checked={method === m.value} onChange={() => setMethod(m.value)} />
              {m.label}
            </label>
          ))}
        </div>
        <Help
          mode={mode}
          text={
            <>
              <p>
                <strong>Standard array:</strong> give each of 15, 14, 13, 12, 10 and 8 to one ability. Quick and balanced.
              </p>
              <p>
                <strong>Point buy:</strong> every score starts at 8 and you spend {options.point_buy.budget} points to raise
                them, up to 15. Higher scores cost more.
              </p>
              <p>Put your highest score in your class's main ability. Your race adds its bonuses on top.</p>
            </>
          }
        />
      </fieldset>
      {method === "point-buy" && (
        <p className={`points-left${left < 0 ? " over" : ""}`} data-testid="points-left">
          {left} of {options.point_buy.budget} points left
        </p>
      )}
      {method && (
        <div className="table-wrap">
          <table className="ability-table">
            <thead>
              <tr>
                <th scope="col">Ability</th>
                <th scope="col">Base</th>
                <th scope="col">Bonus</th>
                <th scope="col">Score</th>
              </tr>
            </thead>
            <tbody>
              {options.abilities.map((a) => {
                const row = sheet.abilities.find((x) => x.key === a.key);
                const current = base[a.key];
                return (
                  <tr key={a.key} data-testid={`ability-row-${a.key}`}>
                    <th scope="row">{a.name}</th>
                    <td>
                      {method === "standard-array" ? (
                        <select
                          aria-label={`${a.name} score`}
                          value={current ?? ""}
                          onChange={(e) => setScore(a.key, e.target.value ? Number(e.target.value) : undefined)}
                        >
                          <option value="">—</option>
                          {options.standard_array
                            .filter((n) => mode === "standard" || n === current || used.filter((u) => u === n).length < options.standard_array.filter((x) => x === n).length)
                            .map((n) => (
                              <option key={n} value={n}>
                                {n}
                              </option>
                            ))}
                        </select>
                      ) : (
                        <span className="stepper">
                          <button
                            type="button"
                            className="btn ghost small"
                            aria-label={`Lower ${a.name}`}
                            disabled={(current ?? 8) <= 8}
                            onClick={() => setScore(a.key, (current ?? 8) - 1)}
                          >
                            −
                          </button>
                          <span className="stepper-value" data-testid={`base-${a.key}`}>
                            {current ?? 8}
                          </span>
                          <button
                            type="button"
                            className="btn ghost small"
                            aria-label={`Raise ${a.name}`}
                            disabled={
                              (current ?? 8) >= 15 ||
                              (mode === "easy" &&
                                (options.point_buy.costs[String((current ?? 8) + 1)] ?? 99) -
                                  (options.point_buy.costs[String(current ?? 8)] ?? 0) >
                                  left)
                            }
                            onClick={() => setScore(a.key, (current ?? 8) + 1)}
                          >
                            +
                          </button>
                        </span>
                      )}
                    </td>
                    <td>{row && row.bonus ? signed(row.bonus) : "—"}</td>
                    <td>
                      <strong data-testid={`score-${a.key}`}>{row?.score ?? "—"}</strong>{" "}
                      <span className="muted small">({row ? signed(row.modifier) : "—"})</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
