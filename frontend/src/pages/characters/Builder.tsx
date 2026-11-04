import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Breadcrumbs } from "../../components/Tome";
import { api } from "../../lib/api";
import {
  BUILD_MODE_LABELS,
  characterPath,
  useCharacterOptions,
  type Build,
  type BuildMode,
  type CharacterDetail,
  type CharacterOptions,
  type CheckResult,
  type Problem,
  type Slot,
} from "../../lib/characters";
import { useFlash } from "../../lib/flash";
import { MODE_LABELS, useEnterMode } from "../../lib/mode";
import { AbilityScores, Help, SlotView, type AbilityScoresValue } from "./builderParts";

/**
 * The character builder: a sheet of paper you fill in.
 *
 * Standard build: free tabs you can jump between, levels 1 to 20, every option shown.
 * Easy build: a guided tutorial, one step at a time, levels 1 to 3, only the options the
 * character can take, help open by default.
 *
 * Every change is sent to /api/characters/check, which answers with the choices still open
 * (slots), the sheet so far and anything the rules refuse. The builder never decides a rule.
 */
type SectionKey = "basics" | "class" | "race" | "abilities" | "background" | "spells" | "equipment" | "review";

const SECTION_TITLES: Record<SectionKey, string> = {
  basics: "Name and level",
  class: "Class",
  race: "Race",
  abilities: "Ability scores",
  background: "Background",
  spells: "Spells",
  equipment: "Equipment",
  review: "Review",
};
const STANDARD_ORDER: SectionKey[] = ["basics", "class", "race", "abilities", "background", "spells", "equipment", "review"];
const EASY_ORDER: SectionKey[] = ["class", "race", "abilities", "background", "spells", "equipment", "basics", "review"];

/** Plain-language pointers for new players. Flavour only: the rules come from the server. */
const CLASS_HINTS: Record<string, string> = {
  barbarian: "A furious warrior who shrugs off hits. Simple to play: hit hard, rage often.",
  bard: "A charming performer whose music is magic. Good at talking, helping and a bit of everything.",
  cleric: "A priest who heals friends and smites foes. A great support character.",
  druid: "A guardian of nature who casts spells and later turns into animals.",
  fighter: "A master of weapons and armour. The easiest class to learn.",
  monk: "A martial artist who fights unarmoured with lightning-fast blows.",
  paladin: "A holy knight in heavy armour who heals and smites. Sturdy and forgiving.",
  ranger: "A hunter and tracker, deadly with a bow, with a little nature magic.",
  rogue: "A sneaky expert who strikes from the shadows and is good with skills.",
  sorcerer: "Born with raw magic. Fewer spells than a wizard, but they bend them to their will.",
  warlock: "Gets magic from a pact with a powerful patron. Simple, strong spells.",
  wizard: "A scholar of magic with the biggest spell list. Powerful but fragile.",
};

export function sectionOf(field: string): SectionKey {
  if (field === "name" || field === "level" || field === "alignment" || field.startsWith("notes")) return "basics";
  if (field === "class" || field === "subclass" || field.startsWith("class:") || field.startsWith("feature:")) return "class";
  if (field === "race" || field === "subrace" || field.startsWith("race:") || field.startsWith("trait:")) return "race";
  if (field === "ability_scores" || field.startsWith("asi:")) return "abilities";
  if (field === "background" || field.startsWith("background:")) return "background";
  if (field.startsWith("spells:")) return "spells";
  return "equipment";
}

/**
 * Picks that belong to a class, race or background. Several slots share an id across classes
 * ("class:proficiency-0" is every class's skill choice, "spells:cantrips" every caster's cantrips),
 * so without this a Cleric's Insight would carry over into the Barbarian's skills as a hidden pick.
 */
const PICKS_OWNED_BY: Partial<Record<keyof Build, string[]>> = {
  class: ["class:", "feature:", "asi:", "spells:", "equipment:class-"],
  race: ["race:", "trait:"],
  background: ["background:", "equipment:background-"],
};

/** Apply a change, dropping the picks of a class, race or background the player switched away from. */
export function withoutStalePicks(build: Build, patch: Partial<Build>): Build {
  const next = { ...build, ...patch };
  const prefixes = Object.entries(PICKS_OWNED_BY)
    .filter(([key]) => key in patch && patch[key as keyof Build] !== build[key as keyof Build])
    .flatMap(([, owned]) => owned ?? []);
  if (!prefixes.length) return next;
  const choices = Object.fromEntries(
    Object.entries(build.choices ?? {}).filter(([slotId]) => !prefixes.some((p) => slotId.startsWith(p))),
  );
  return { ...next, choices };
}

/** What the check endpoint is sent: half-assigned ability scores count as not chosen yet. */
function forCheck(build: Build): Build {
  const scores = build.ability_scores;
  if (scores?.base && Object.keys(scores.base).length < 6) return { ...build, ability_scores: { method: scores.method } };
  return build;
}

function useLiveCheck(build: Build | null, mode: BuildMode) {
  const [result, setResult] = useState<CheckResult | null>(null);
  const seq = useRef(0);
  useEffect(() => {
    if (!build) return;
    const n = ++seq.current;
    const timer = setTimeout(async () => {
      const res = await api.post<CheckResult>("/api/characters/check", { build: forCheck(build), build_mode: mode });
      if (res.ok && n === seq.current) setResult(res.data);
    }, 150);
    return () => clearTimeout(timer);
  }, [build, mode]);
  return result;
}

export function Builder() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const editing = id !== undefined;
  useEnterMode("player");
  const options = useCharacterOptions();
  const { flash } = useFlash();
  const navigate = useNavigate();

  const [build, setBuild] = useState<Build | null>(editing ? null : { name: "", level: 1, choices: {} });
  const [mode, setMode] = useState<BuildMode>(params.get("mode") === "easy" ? "easy" : "standard");
  const [name, setName] = useState("New character");
  const [loadError, setLoadError] = useState<string | null>(null);
  // ?section=spells opens the builder on that page, e.g. from a character's spellbook
  const asked = params.get("section") as SectionKey | null;
  const startSection = (m: BuildMode): SectionKey => (asked && asked in SECTION_TITLES ? asked : m === "easy" ? "class" : "basics");
  const [section, setSection] = useState<SectionKey>(startSection(mode));
  const [saving, setSaving] = useState(false);
  const [saveErrors, setSaveErrors] = useState<Problem[]>([]);
  const [startLevel, setStartLevel] = useState(0);
  const result = useLiveCheck(build, mode);

  useEffect(() => {
    if (!editing) return;
    void api.get<CharacterDetail>(`/api/characters/${id}`).then((res) => {
      if (!res.ok) {
        setLoadError(res.status === 404 ? "Character not found." : res.data.error ?? "Couldn't open the character.");
        return;
      }
      setBuild(res.data.character.build);
      setMode(res.data.character.build_mode);
      setName(res.data.character.name);
      setStartLevel(res.data.character.level);
      setSection(startSection(res.data.character.build_mode));
    });
  }, [editing, id]);

  const hasSpells = Boolean(result?.slots.some((s) => s.group === "spells"));
  const order = (mode === "easy" ? EASY_ORDER : STANDARD_ORDER).filter((s) => s !== "spells" || hasSpells || mode === "standard");

  const status = useMemo(() => {
    const out: Record<string, { missing: number; errors: number }> = {};
    for (const key of STANDARD_ORDER) out[key] = { missing: 0, errors: 0 };
    for (const m of result?.missing ?? []) out[sectionOf(m.field)].missing++;
    for (const e of result?.errors ?? []) out[sectionOf(e.field)].errors++;
    return out;
  }, [result]);

  const trail = [
    { label: "Guild Hall", to: "/guild-hall" },
    { label: MODE_LABELS.player, to: "/guild-hall" },
    { label: "Character Manager", to: "/play/characters/my-characters" },
    ...(editing ? [{ label: name, to: characterPath(Number(id)) }, { label: "Builder" }] : [{ label: "New character" }]),
  ];

  if (loadError) {
    return (
      <>
        <Breadcrumbs trail={trail} />
        <div className="card narrow center" data-testid="character-missing">
          <h1>{loadError}</h1>
          <Link to="/play/characters/my-characters" className="btn ghost">
            Back to my characters
          </Link>
        </div>
      </>
    );
  }
  if (!build || !options) return <p className="muted center">Sharpening the quill…</p>;

  const update = (patch: Partial<Build>) => {
    setSaveErrors([]);
    setBuild((b) => withoutStalePicks(b as Build, patch));
  };
  const setChoice = (slotId: string, values: string[]) => {
    setSaveErrors([]);
    setBuild((b) => ({ ...(b as Build), choices: { ...(b?.choices ?? {}), [slotId]: values } }));
  };

  async function save() {
    if (!build) return;
    setSaving(true);
    const body = { build: forCheck(build), build_mode: mode };
    const res = editing
      ? await api.patch<CharacterDetail>(`/api/characters/${id}`, body)
      : await api.post<CharacterDetail>("/api/characters", body);
    setSaving(false);
    if (!res.ok) {
      const problems = (res.data as unknown as { errors?: Problem[] }).errors;
      setSaveErrors(problems ?? [{ field: "build", message: res.data.error ?? "The character wasn't saved." }]);
      return;
    }
    const saved = res.data.character;
    flash(
      "success",
      saved.status === "complete" ? `${saved.name} is ready for adventure.` : `${saved.name} was saved as a draft.`,
      { afterNavigate: true },
    );
    navigate(characterPath(saved.id));
  }

  const index = order.indexOf(section);
  const errorsHere = result?.errors.filter((e) => sectionOf(e.field) === section) ?? [];
  const slotsHere = (result?.slots ?? []).filter((s) => sectionOf(s.id) === section);
  const pageProps: PageProps = { build, options, result, mode, update, setChoice, slots: slotsHere, maxLevel: mode === "easy" ? Math.max(options.easy_max_level, startLevel) : options.max_level };

  return (
    <>
      <Breadcrumbs trail={trail} />
      <div className={`builder card mode-${mode}`} data-testid="builder">
        <header className="builder-header">
          <div>
            <p className="tome-eyebrow">{BUILD_MODE_LABELS[mode]}</p>
            <h1>{editing ? `Editing ${name}` : "A new character"}</h1>
            <p className="muted">
              {mode === "easy"
                ? "One step at a time. Only the choices your character can take are shown, and help is open on every step."
                : "Fill in the tabs in any order. Every option is shown; the rules refuse the ones you can't take."}
            </p>
          </div>
          <div className="builder-actions">
            <button type="button" className="btn primary" onClick={save} disabled={saving || !result}>
              {saving ? "Saving…" : editing ? "Save changes" : "Save character"}
            </button>
            <p className="small muted" data-testid="builder-status">
              {!result
                ? "Checking the rules…"
                : result.complete
                  ? "Complete: ready to play."
                  : result.valid
                    ? `${result.missing.length} choice${result.missing.length === 1 ? "" : "s"} left. You can save a draft.`
                    : `${result.errors.length} problem${result.errors.length === 1 ? "" : "s"} to fix.`}
            </p>
          </div>
        </header>

        {mode === "easy" ? (
          <ol className="wizard-steps" aria-label="Steps">
            {order.map((key, i) => (
              <li key={key} className={key === section ? "current" : i < index ? "done" : undefined} aria-current={key === section ? "step" : undefined}>
                <span className="step-num">{i + 1}</span> {SECTION_TITLES[key]}
              </li>
            ))}
          </ol>
        ) : (
          <div className="builder-tabs" role="tablist" aria-label="Builder sections">
            {order.map((key) => {
              const st = status[key];
              return (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  id={`tab-${key}`}
                  aria-selected={key === section}
                  aria-controls="builder-panel"
                  className={`builder-tab${key === section ? " current" : ""}`}
                  onClick={() => setSection(key)}
                >
                  {SECTION_TITLES[key]}
                  {key !== "review" && result && (
                    <span className={`tab-mark${st.errors ? " bad" : st.missing ? " open" : " done"}`} data-testid={`tab-mark-${key}`}>
                      {st.errors ? "!" : st.missing ? st.missing : "✓"}
                      <span className="sr-only">
                        {st.errors ? " problems" : st.missing ? " choices left" : " done"}
                      </span>
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}

        <section
          id="builder-panel"
          className="builder-panel"
          role={mode === "standard" ? "tabpanel" : undefined}
          aria-labelledby={mode === "standard" ? `tab-${section}` : "step-title"}
          data-testid={`section-${section}`}
        >
          <h2 id="step-title" className="page-title">
            {SECTION_TITLES[section]}
          </h2>
          {(saveErrors.length > 0 || errorsHere.length > 0) && (
            <div className="form-error-summary" role="alert" data-testid="builder-errors">
              <ul>
                {(saveErrors.length ? saveErrors : errorsHere).map((e, i) => (
                  <li key={i}>{e.message}</li>
                ))}
              </ul>
            </div>
          )}
          {section === "basics" && <BasicsPage {...pageProps} />}
          {section === "class" && <ClassPage {...pageProps} />}
          {section === "race" && <RacePage {...pageProps} />}
          {section === "abilities" && <AbilitiesPage {...pageProps} />}
          {section === "background" && <BackgroundPage {...pageProps} />}
          {section === "spells" && <SpellsPage {...pageProps} />}
          {section === "equipment" && <EquipmentPage {...pageProps} />}
          {section === "review" && <ReviewPage {...pageProps} goTo={setSection} />}
        </section>

        {mode === "easy" && (
          <nav className="wizard-nav" aria-label="Steps">
            {index > 0 ? (
              <button type="button" className="btn ghost" onClick={() => setSection(order[index - 1])}>
                ← Back
              </button>
            ) : (
              <span />
            )}
            {index < order.length - 1 && (
              <button type="button" className="btn primary" onClick={() => setSection(order[index + 1])}>
                Next: {SECTION_TITLES[order[index + 1]]} →
              </button>
            )}
          </nav>
        )}
      </div>
    </>
  );
}

// ---------------------------------------------------------------- pages
interface PageProps {
  build: Build;
  options: CharacterOptions;
  result: CheckResult | null;
  mode: BuildMode;
  slots: Slot[];
  maxLevel: number;
  update: (patch: Partial<Build>) => void;
  setChoice: (slotId: string, values: string[]) => void;
}

function Slots({ slots, build, mode, setChoice }: Pick<PageProps, "slots" | "build" | "mode" | "setChoice">) {
  return (
    <>
      {slots.map((s) => (
        <SlotView key={s.id} slot={s} mode={mode} selected={build.choices?.[s.id] ?? []} onChange={(v) => setChoice(s.id, v)} />
      ))}
    </>
  );
}

function Pending({ children }: { children: ReactNode }) {
  return <p className="empty-page">{children}</p>;
}

function CardChoice({
  name,
  value,
  checked,
  title,
  onSelect,
  children,
}: {
  name: string;
  value: string;
  checked: boolean;
  title: string;
  onSelect: () => void;
  children?: ReactNode;
}) {
  return (
    <label className={`choice-card${checked ? " on" : ""}`} data-testid={`choice-${value}`}>
      <input type="radio" name={name} value={value} checked={checked} onChange={onSelect} />
      <span className="choice-title">{title}</span>
      {children && <span className="choice-body">{children}</span>}
    </label>
  );
}

function BasicsPage({ build, options, mode, update, maxLevel }: PageProps) {
  return (
    <div className="stack">
      <div className="field">
        <label htmlFor="character-name">Character name</label>
        <input id="character-name" value={build.name ?? ""} maxLength={60} onChange={(e) => update({ name: e.target.value })} />
      </div>
      <div className="field">
        <label htmlFor="character-level">Starting level</label>
        <select id="character-level" value={build.level ?? 1} onChange={(e) => update({ level: Number(e.target.value) })}>
          {Array.from({ length: maxLevel }, (_, i) => i + 1).map((l) => (
            <option key={l} value={l}>
              Level {l}
            </option>
          ))}
        </select>
        <Help
          mode={mode}
          text={
            mode === "easy"
              ? `Easy build creates characters up to level ${options.easy_max_level}, so you don't face every level's choices at once. Your character can still reach level 20 later.`
              : "The level your character starts at. Each level adds hit points and new features, and some add choices."
          }
        />
      </div>
      <div className="field">
        <label htmlFor="character-alignment">Alignment</label>
        <select id="character-alignment" value={build.alignment ?? ""} onChange={(e) => update({ alignment: e.target.value || null })}>
          <option value="">Choose…</option>
          {options.alignments.map((a) => (
            <option key={a.index} value={a.index}>
              {a.name}
            </option>
          ))}
        </select>
        <Help mode={mode} text="Your character's moral compass: lawful or chaotic, good or evil. It's a roleplaying guide, not a rule." />
      </div>
    </div>
  );
}

function ClassPage({ build, options, result, mode, update, slots, setChoice }: PageProps) {
  const cls = options.classes.find((c) => c.index === build.class);
  const level = build.level ?? 1;
  return (
    <div className="stack">
      <fieldset className="field">
        <legend>Choose a class</legend>
        <Help mode={mode} text="Your class is what your character does: fights, casts spells, sneaks or heals. It decides your hit points, skills and features." />
        <div className="choice-grid">
          {options.classes.map((c) => (
            <CardChoice
              key={c.index}
              name="class"
              value={c.index}
              title={c.name}
              checked={build.class === c.index}
              onSelect={() => update({ class: c.index, subclass: null })}
            >
              {mode === "easy" && <span className="small">{CLASS_HINTS[c.index]}</span>}
              <span className="small muted">
                Hit die d{c.hit_die} · saves {c.saving_throws.map((s) => s.toUpperCase()).join(", ")}
                {c.spellcaster ? " · spellcaster" : ""}
              </span>
            </CardChoice>
          ))}
        </div>
      </fieldset>
      {cls && level >= cls.subclass_level && (
        <fieldset className="field">
          <legend>Subclass</legend>
          <Help mode={mode} text={`${cls.name}s choose a subclass at level ${cls.subclass_level}. It shapes the features you gain as you level up.`} />
          <div className="choice-grid">
            {cls.subclasses.map((s) => (
              <CardChoice key={s.index} name="subclass" value={s.index} title={s.name} checked={build.subclass === s.index} onSelect={() => update({ subclass: s.index })}>
                <span className="small">{s.desc}</span>
              </CardChoice>
            ))}
          </div>
        </fieldset>
      )}
      {cls && level < cls.subclass_level && (
        <p className="hint">
          {cls.name}s choose a subclass at level {cls.subclass_level}.
        </p>
      )}
      {!build.class ? <Pending>Pick a class to see its choices.</Pending> : !result ? null : <Slots slots={slots} build={build} mode={mode} setChoice={setChoice} />}
    </div>
  );
}

function RacePage({ build, options, mode, update, slots, setChoice }: PageProps) {
  const race = options.races.find((r) => r.index === build.race);
  return (
    <div className="stack">
      <fieldset className="field">
        <legend>Choose a race</legend>
        <Help mode={mode} text="Your race gives ability score bonuses, a walking speed, languages and special traits like darkvision." />
        <div className="choice-grid">
          {options.races.map((r) => (
            <CardChoice
              key={r.index}
              name="race"
              value={r.index}
              title={r.name}
              checked={build.race === r.index}
              onSelect={() => update({ race: r.index, subrace: r.subraces.length === 1 && mode === "easy" ? r.subraces[0].index : null })}
            >
              <span className="small muted">
                {r.ability_bonuses.map((b) => `${b.ability.toUpperCase()} +${b.bonus}`).join(", ") || "Bonuses of your choice"} · speed {r.speed} ft
              </span>
              {mode === "easy" && r.traits.length > 0 && <span className="small">{r.traits.join(", ")}</span>}
            </CardChoice>
          ))}
        </div>
      </fieldset>
      {race && race.subraces.length > 0 && (
        <fieldset className="field">
          <legend>Subrace</legend>
          <div className="choice-grid">
            {race.subraces.map((s) => (
              <CardChoice key={s.index} name="subrace" value={s.index} title={s.name} checked={build.subrace === s.index} onSelect={() => update({ subrace: s.index })}>
                <span className="small">{s.desc}</span>
              </CardChoice>
            ))}
          </div>
        </fieldset>
      )}
      {!build.race ? <Pending>Pick a race to see its choices.</Pending> : <Slots slots={slots} build={build} mode={mode} setChoice={setChoice} />}
    </div>
  );
}

function AbilitiesPage({ build, options, result, mode, update, slots, setChoice }: PageProps) {
  const cls = options.classes.find((c) => c.index === build.class);
  return (
    <div className="stack">
      {mode === "easy" && cls && (
        <p className="notice">
          Tip: {cls.name}s rely on{" "}
          <strong>
            {cls.spellcasting_ability ? cls.spellcasting_ability.toUpperCase() : cls.saving_throws[0].toUpperCase()}
          </strong>
          . Put your highest score there.
        </p>
      )}
      {result && (
        <AbilityScores
          value={(build.ability_scores ?? {}) as AbilityScoresValue}
          options={options}
          sheet={result.sheet}
          mode={mode}
          onChange={(v) => update({ ability_scores: v })}
        />
      )}
      <Slots slots={slots} build={build} mode={mode} setChoice={setChoice} />
    </div>
  );
}

function BackgroundPage({ build, options, mode, update, slots, setChoice }: PageProps) {
  return (
    <div className="stack">
      <fieldset className="field">
        <legend>Choose a background</legend>
        <Help mode={mode} text="Your background is what your character did before adventuring. It gives two skills, languages or tools, some equipment and a feature." />
        <div className="choice-grid">
          {options.backgrounds.map((b) => (
            <CardChoice key={b.index} name="background" value={b.index} title={b.name} checked={build.background === b.index} onSelect={() => update({ background: b.index })}>
              <span className="small muted">
                Skills: {b.skills.join(", ")}
                {b.feature ? ` · ${b.feature}` : ""}
              </span>
            </CardChoice>
          ))}
        </div>
        <p className="hint">The free rules include one background. More arrive with homebrew.</p>
      </fieldset>
      <Slots slots={slots} build={build} mode={mode} setChoice={setChoice} />
    </div>
  );
}

function SpellsPage({ build, result, mode, slots, setChoice }: PageProps) {
  if (!build.class) return <Pending>Pick a class first: your class decides which spells you can learn.</Pending>;
  if (result && slots.length === 0) {
    return <Pending>{result.sheet.summary.class}s don't cast spells at level {build.level ?? 1}.</Pending>;
  }
  return (
    <div className="stack">
      {result?.sheet.spellcasting && (
        <p className="muted">
          Spellcasting ability {result.sheet.spellcasting.ability_name} · save DC {result.sheet.spellcasting.save_dc} · highest spell level{" "}
          {result.sheet.spellcasting.max_spell_level}
        </p>
      )}
      <Slots slots={slots} build={build} mode={mode} setChoice={setChoice} />
    </div>
  );
}

function EquipmentPage({ build, result, mode, update, slots, setChoice }: PageProps) {
  if (!build.class && !build.background) return <Pending>Pick a class and background to see your starting equipment.</Pending>;
  const armor = (result?.sheet.inventory ?? []).filter((i) => i.category === "Armor");
  const bodyArmor = armor.filter((i) => i.index !== "shield");
  const hasShield = armor.some((i) => i.index === "shield");
  const equipped = build.equipped ?? result?.sheet.equipped ?? { armor: null, shield: null };
  return (
    <div className="stack">
      <Help mode={mode} text="Your class and background each give you starting equipment. Where there's a choice, pick one option." />
      <Slots slots={slots} build={build} mode={mode} setChoice={setChoice} />
      {(bodyArmor.length > 0 || hasShield) && (
        <fieldset className="field">
          <legend>What are you wearing?</legend>
          {bodyArmor.length > 0 && (
            <div className="field">
              <label htmlFor="equip-armor">Armour</label>
              <select
                id="equip-armor"
                value={equipped.armor ?? ""}
                onChange={(e) => update({ equipped: { ...equipped, armor: e.target.value || null } })}
              >
                <option value="">No armour</option>
                {bodyArmor.map((i) => (
                  <option key={i.index} value={i.index}>
                    {i.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          {hasShield && (
            <label className="check">
              <input
                type="checkbox"
                checked={equipped.shield === "shield"}
                onChange={(e) => update({ equipped: { ...equipped, shield: e.target.checked ? "shield" : null } })}
              />
              Carry a shield
            </label>
          )}
          {result && (
            <p className="muted" data-testid="builder-ac">
              Armour class {result.sheet.armor_class} ({result.sheet.armor_class_note})
            </p>
          )}
        </fieldset>
      )}
    </div>
  );
}

function ReviewPage({ result, goTo }: PageProps & { goTo: (s: SectionKey) => void }) {
  if (!result) return null;
  const s = result.sheet;
  return (
    <div className="stack" data-testid="review">
      <p className="character-line">
        {s.summary.name || "Unnamed"}: level {s.summary.level} {s.summary.subrace ?? s.summary.race ?? "?"} {s.summary.class ?? "?"}
        {s.summary.subclass ? ` (${s.summary.subclass})` : ""}
      </p>
      <ul className="stat-row">
        <li className="stat">
          <span className="stat-value">{s.armor_class}</span>
          <span className="stat-label">Armour class</span>
        </li>
        <li className="stat">
          <span className="stat-value">{s.hit_points}</span>
          <span className="stat-label">Hit points</span>
        </li>
        <li className="stat">
          <span className="stat-value">{s.speed} ft</span>
          <span className="stat-label">Speed</span>
        </li>
      </ul>
      {result.complete ? (
        <p className="notice" data-testid="review-complete">
          Every choice is made. Save your character and it's ready for adventure.
        </p>
      ) : (
        <>
          <h3 className="leaf-heading">Still to do</h3>
          <ul className="todo-list" data-testid="review-missing">
            {[...result.errors, ...result.missing].map((m, i) => (
              <li key={i}>
                <button type="button" className="link-button" onClick={() => goTo(sectionOf(m.field))}>
                  {SECTION_TITLES[sectionOf(m.field)]}
                </button>
                : {m.message}
              </li>
            ))}
          </ul>
          <p className="hint">You can save now and finish later: unfinished characters are kept as drafts.</p>
        </>
      )}
    </div>
  );
}
