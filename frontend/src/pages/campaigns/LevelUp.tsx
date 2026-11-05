import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Breadcrumbs } from "../../components/Tome";
import { api } from "../../lib/api";
import { useCharacterOptions, type Build, type CheckResult, type HpMethod, type Problem } from "../../lib/characters";
import { playerCampaignPath, type InstanceDetail, type LevelUpPreview } from "../../lib/campaigns";
import { useFlash } from "../../lib/flash";
import { MODE_LABELS, useEnterMode } from "../../lib/mode";
import { SlotView } from "../characters/builderParts";

/**
 * Level Up: one level at a time, the way the rules agreed with Connor describe it.
 *
 * The app works out everything that changes on its own (hit points, proficiency bonus, new
 * features, spell slots, how many spells you know) and only asks for the new level's picks: a
 * subclass when it unlocks, an ability score improvement or feat, new spells, invocations... Earlier
 * picks are locked, except the swaps the rules allow. Then the player gains hit points the ways the
 * DM allows: the average, the maximum, or a roll the app makes once.
 */
type Data = InstanceDetail & { level_up: LevelUpPreview };

export function LevelUpPage() {
  const { campaignId } = useParams();
  const id = Number(campaignId);
  useEnterMode("player");
  const options = useCharacterOptions();
  const { flash } = useFlash();
  const navigate = useNavigate();
  const url = `/api/campaigns/${id}/instance/level-up`;
  const backUrl = playerCampaignPath(id, "character");

  const [data, setData] = useState<Data | null>(null);
  const [missing, setMissing] = useState<string | null>(null);
  const [build, setBuild] = useState<Build | null>(null);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [hpMethod, setHpMethod] = useState<HpMethod | null>(null);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    void api.get<Data>(url).then((res) => {
      if (!res.ok) {
        setMissing(res.data.error ?? "Your character couldn't be found.");
        return;
      }
      setData(res.data);
      setBuild(res.data.level_up.build ?? null);
      const methods = res.data.level_up.hp?.methods ?? [];
      setHpMethod(methods.length === 1 ? methods[0].value : null);
    });
  }, [url]);

  // Ask the rules engine about the picks as they change (the builder never decides a rule)
  useEffect(() => {
    if (!build) return;
    const n = ++seq.current;
    const timer = setTimeout(async () => {
      const res = await api.post<CheckResult>("/api/characters/check", { build, previous_level: 20 });
      if (res.ok && n === seq.current) setCheck(res.data);
    }, 150);
    return () => clearTimeout(timer);
  }, [build]);

  const preview = data?.level_up;
  const before = data?.instance.build;
  const openSlots = useMemo(
    () => (check?.slots ?? []).filter((s) => preview?.open_slots?.includes(s.id)),
    [check, preview],
  );

  const trail = [
    { label: "Guild Hall", to: "/guild-hall" },
    { label: MODE_LABELS.player, to: "/guild-hall" },
    { label: "Campaigns", to: "/play/campaigns/current" },
    { label: data?.instance.campaign.name ?? "Campaign", to: backUrl },
    { label: "Level up" },
  ];

  if (missing) {
    return (
      <>
        <Breadcrumbs trail={trail} />
        <div className="card narrow center" data-testid="level-up-missing">
          <h1>{missing}</h1>
          <Link to={backUrl} className="btn ghost">
            Back to the campaign
          </Link>
        </div>
      </>
    );
  }
  if (!data || !preview || !options) return <p className="muted center">Sharpening the quill…</p>;
  const i = data.instance;

  if (!preview.allowed || !build || !preview.hp) {
    return (
      <>
        <Breadcrumbs trail={trail} />
        <div className="card narrow center" data-testid="level-up-blocked">
          <h1>Not yet</h1>
          <p>{preview.reason}</p>
          <Link to={backUrl} className="btn ghost">
            Back to {i.name}
          </Link>
        </div>
      </>
    );
  }

  const cls = options.classes.find((c) => c.index === build.class);
  const lockedPicks = (slotId: string) => before?.choices?.[slotId] ?? [];

  function setChoice(slotId: string, values: string[]) {
    // Earlier picks are locked: at most one swap where the rules allow it, none anywhere else
    const removed = lockedPicks(slotId).filter((v) => !values.includes(v));
    const swap = preview?.swaps?.[slotId];
    if (removed.length && slotId !== "spells:prepared" && (!swap || removed.length > 1)) {
      setNotice(
        swap
          ? `You can swap one ${swap} per level. Put the other one back first.`
          : "That was picked at an earlier level. Earlier picks are locked in a campaign.",
      );
      return;
    }
    setNotice(null);
    setProblems([]);
    setBuild((b) => ({ ...(b as Build), choices: { ...(b?.choices ?? {}), [slotId]: values } }));
  }

  async function rollHp() {
    const res = await api.post<{ level_up: LevelUpPreview }>(`${url}/hp-roll`);
    if (!res.ok) {
      flash("error", res.data.error ?? "The die wouldn't roll.");
      return;
    }
    setData((d) => (d ? { ...d, level_up: { ...d.level_up, hp: res.data.level_up.hp } } : d));
    setHpMethod("roll");
  }

  async function confirm() {
    if (!build || !hpMethod) return;
    setSaving(true);
    const res = await api.post<InstanceDetail & { message: string }>(url, { build, hp_method: hpMethod });
    setSaving(false);
    if (!res.ok) {
      const errors = (res.data as unknown as { errors?: Problem[] | Record<string, string> }).errors;
      const list = Array.isArray(errors)
        ? errors
        : errors
          ? Object.entries(errors).map(([field, message]) => ({ field, message }))
          : [{ field: "level", message: res.data.error ?? "The level-up didn't work." }];
      setProblems(list);
      return;
    }
    flash("success", res.data.message, { afterNavigate: true });
    navigate(backUrl);
  }

  const hp = preview.hp;
  const chosenMethod = hp.methods.find((m) => m.value === hpMethod);
  const unfinished = (check?.missing ?? []).length > 0 || (check?.errors ?? []).length > 0;

  return (
    <>
      <Breadcrumbs trail={trail} />
      <div className="builder card level-up" data-testid="level-up">
        <header className="builder-header">
          <div>
            <p className="tome-eyebrow">{i.campaign.name}</p>
            <h1>
              {i.name} reaches level {preview.level}
            </h1>
            {preview.roadmap && (
              <p className="hint" data-testid="level-up-roadmap">
                Following “{preview.roadmap.name}”: its picks for level {preview.level} are filled in. Changing them stops
                following the roadmap.
              </p>
            )}
          </div>
        </header>

        <section className="level-up-step" aria-labelledby="auto-heading">
          <h2 id="auto-heading" className="leaf-heading">
            What changes on its own
          </h2>
          {preview.changes && preview.changes.length > 0 ? (
            <ul className="level-up-changes" data-testid="level-up-changes">
              {preview.changes.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">Nothing else changes at this level, apart from your hit points.</p>
          )}
        </section>

        <section className="level-up-step" aria-labelledby="picks-heading">
          <h2 id="picks-heading" className="leaf-heading">
            Your picks for level {preview.level}
          </h2>
          {preview.subclass_unlocks && cls && (
            <fieldset className="field" data-testid="level-up-subclass">
              <legend>Choose your {cls.name.toLowerCase()} subclass</legend>
              <div className="choice-grid">
                {cls.subclasses.map((s) => (
                  <label key={s.index} className={`choice-card${build.subclass === s.index ? " on" : ""}`}>
                    <input
                      type="radio"
                      name="subclass"
                      value={s.index}
                      checked={build.subclass === s.index}
                      onChange={() => setBuild({ ...build, subclass: s.index })}
                    />
                    <strong>{s.name}</strong>
                    <span className="small muted">{s.desc.slice(0, 160)}…</span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          {notice && (
            <p className="field-error" role="alert" data-testid="lock-notice">
              {notice}
            </p>
          )}
          {openSlots.length === 0 && !preview.subclass_unlocks ? (
            <p className="muted" data-testid="no-picks">
              No choices to make at this level.
            </p>
          ) : (
            openSlots.map((s) => (
              <div key={s.id} className="level-up-slot" data-testid={`level-up-slot-${s.id}`}>
                {preview.swaps?.[s.id] && (
                  <p className="hint">You may swap one {preview.swaps[s.id]} for another as you level up.</p>
                )}
                {s.id === "spells:prepared" && (
                  <p className="hint">Prepared spells can change at any time, not just now.</p>
                )}
                <SlotView slot={s} mode={i.build_mode} selected={build.choices?.[s.id] ?? []} onChange={(v) => setChoice(s.id, v)} />
              </div>
            ))
          )}
        </section>

        <section className="level-up-step" aria-labelledby="hp-heading">
          <h2 id="hp-heading" className="leaf-heading">
            Hit points
          </h2>
          <p className="hint">
            Your hit die is a d{hp.hit_die}, plus your Constitution modifier ({hp.con_modifier >= 0 ? "+" : "−"}
            {Math.abs(hp.con_modifier)}). Your Dungeon Master allows: {hp.methods.map((m) => m.label.toLowerCase()).join(", ")}.
          </p>
          <div className="hp-methods" role="radiogroup" aria-label="How to gain hit points">
            {hp.methods.map((m) => (
              <label key={m.value} className={`choice-card${hpMethod === m.value ? " on" : ""}`} data-testid={`hp-${m.value}`}>
                <input
                  type="radio"
                  name="hp-method"
                  value={m.value}
                  checked={hpMethod === m.value}
                  disabled={m.value === "roll" && m.die === null}
                  onChange={() => setHpMethod(m.value)}
                />
                <strong>{m.label}</strong>
                <span className="small">
                  {m.die === null ? "Roll the die to find out" : `${m.die} on the die: +${m.gain} hit points`}
                </span>
                {m.value === "roll" && m.die === null && (
                  <button type="button" className="btn ghost small" onClick={rollHp}>
                    Roll a d{hp.hit_die}
                  </button>
                )}
              </label>
            ))}
          </div>
          {hp.rolled !== null && <p className="hint">The roll is kept: it can't be rolled again.</p>}
        </section>

        {(problems.length > 0 || (check?.errors.length ?? 0) > 0) && (
          <ul className="form-error-summary" role="alert" data-testid="level-up-errors">
            {[...problems, ...(check?.errors ?? [])].map((p, n) => (
              <li key={n}>{p.message}</li>
            ))}
          </ul>
        )}
        <div className="row between wrap builder-footer">
          <Link to={backUrl} className="btn ghost">
            Not now
          </Link>
          <div className="row wrap">
            {check && check.missing.length > 0 && (
              <span className="muted small" data-testid="picks-left">
                {check.missing.length} {check.missing.length === 1 ? "choice" : "choices"} left
              </span>
            )}
            <button
              type="button"
              className="btn primary"
              disabled={saving || !chosenMethod || chosenMethod.die === null || unfinished}
              onClick={confirm}
            >
              Level up to {preview.level}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
