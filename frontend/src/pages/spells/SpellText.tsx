import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../../lib/api";
import { capitalise } from "../../lib/bestiary";
import { componentsLine, spellLine, type Spell } from "../../lib/spells";

/**
 * Spells as they're written in the tome, shared by the DM's spell catalogue, the builder's spell
 * picker and a character's spellbook.
 */

// ---------------------------------------------------------------- rules text
/** The SRD text uses a little Markdown: **bold**, *italic*, "- " lists, "## " headings and | tables. */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const pattern = /\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*/g;
  let last = 0;
  let k = 0;
  for (const m of text.matchAll(pattern)) {
    if (m.index! > last) out.push(text.slice(last, m.index));
    if (m[1]) out.push(<strong key={k++}><em>{m[1]}</em></strong>);
    else if (m[2]) out.push(<strong key={k++}>{m[2]}</strong>);
    else out.push(<em key={k++}>{m[3]}</em>);
    last = m.index! + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const cells = (row: string) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

export function RulesText({ paragraphs }: { paragraphs: string[] }) {
  const blocks: ReactNode[] = [];
  for (let i = 0; i < paragraphs.length; i++) {
    const p = paragraphs[i];
    if (p.startsWith("|")) {
      const rows: string[] = [];
      while (i < paragraphs.length && paragraphs[i].startsWith("|")) rows.push(paragraphs[i++]);
      i--;
      const [head, ...body] = rows.filter((r) => !/^\|[\s|:-]+\|?$/.test(r));
      blocks.push(
        <div className="table-wrap" key={i}>
          <table className="rules-table">
            <thead>
              <tr>{cells(head).map((c, j) => <th key={j} scope="col">{inline(c)}</th>)}</tr>
            </thead>
            <tbody>
              {body.map((r, n) => (
                <tr key={n}>{cells(r).map((c, j) => <td key={j}>{inline(c)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
    } else if (p.startsWith("- ")) {
      const items: string[] = [];
      while (i < paragraphs.length && paragraphs[i].startsWith("- ")) items.push(paragraphs[i++].slice(2));
      i--;
      blocks.push(
        <ul key={i}>
          {items.map((it, n) => <li key={n}>{inline(it)}</li>)}
        </ul>,
      );
    } else if (p.startsWith("#")) {
      blocks.push(<h4 key={i} className="rules-heading">{p.replace(/^#+\s*/, "")}</h4>);
    } else {
      blocks.push(<p key={i}>{inline(p)}</p>);
    }
  }
  return <>{blocks}</>;
}

// ---------------------------------------------------------------- one spell
function scaling(spell: Spell): [string, string] | null {
  const dice = (table: Record<string, string>, label: string) =>
    Object.entries(table).map(([lvl, d]) => `${d} (${label} ${lvl})`).join(", ");
  const rows = (spell.damage ?? []).flatMap((dmg) => {
    const type = dmg.damage_type ? ` ${dmg.damage_type.name.toLowerCase()}` : "";
    if (dmg.damage_at_slot_level) return [`${dice(dmg.damage_at_slot_level, "slot")}${type}`];
    if (dmg.damage_at_character_level) return [`${dice(dmg.damage_at_character_level, "level")}${type}`];
    return [];
  });
  if (rows.length) return ["Damage", rows.join("; ")];
  if (spell.heal_at_slot_level) return ["Healing", dice(spell.heal_at_slot_level, "slot").replace(/MOD/g, "mod")];
  return null;
}

/** A spell written out in full: the header lines, the rules text and who can learn it. */
export function SpellBlock({
  spell,
  heading = "h2",
  actions,
}: {
  spell: Spell;
  heading?: "h2" | "h4";
  actions?: ReactNode;
}) {
  const Title = heading;
  const lines: [string, string][] = [
    ["Casting Time", spell.ritual ? `${spell.casting_time} (or as a ritual)` : spell.casting_time],
    ["Range", spell.area_of_effect ? `${spell.range} (${spell.area_of_effect.size}-foot ${spell.area_of_effect.type})` : spell.range],
    ["Components", componentsLine(spell)],
    ["Duration", spell.concentration ? spell.duration.replace(/^Up to/, "Concentration, up to") : spell.duration],
  ];
  const extra: [string, string][] = [];
  if (spell.attack_type) extra.push(["Attack", `${capitalise(spell.attack_type)} spell attack`]);
  if (spell.dc) {
    const success = spell.dc.dc_success === "half" ? "half on a success" : spell.dc.dc_success === "none" ? "no effect on a success" : "see text";
    extra.push(["Saving Throw", `${spell.dc.dc_type.name} (${success})`]);
  }
  const scale = scaling(spell);
  if (scale) extra.push(scale);

  return (
    <article className="spell-block" data-testid="spell-block" aria-labelledby={heading === "h2" ? "page-title" : undefined}>
      <header className="row between wrap">
        <div>
          <Title id={heading === "h2" ? "page-title" : undefined} className={heading === "h2" ? "page-title" : "spell-block-title"}>
            {spell.name}
          </Title>
          <p className="creature-line" data-testid="spell-line">
            {spellLine({ level: spell.level, school: spell.school.name, ritual: spell.ritual })}
          </p>
        </div>
        {actions}
      </header>
      <hr className="tapered" />
      <dl className="stat-lines">
        {lines.map(([label, value]) => (
          <div key={label} data-testid={`spell-${label.toLowerCase().replace(/ /g, "-")}`}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <hr className="tapered" />
      <div className="spell-text" data-testid="spell-text">
        <RulesText paragraphs={spell.desc} />
        {spell.higher_level && spell.higher_level.length > 0 && (
          <div data-testid="spell-higher-level">
            <p>
              <strong>
                <em>{spell.level === 0 ? "Cantrip upgrade." : "At Higher Levels."}</em>
              </strong>{" "}
              {spell.higher_level[0]}
            </p>
            {spell.higher_level.length > 1 && <RulesText paragraphs={spell.higher_level.slice(1)} />}
          </div>
        )}
      </div>
      {extra.length > 0 && (
        <dl className="stat-lines spell-extra">
          {extra.map(([label, value]) => (
            <div key={label} data-testid={`spell-${label.toLowerCase().replace(/ /g, "-")}`}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
      <hr className="tapered" />
      <dl className="stat-lines">
        <div data-testid="spell-classes">
          <dt>Classes</dt>
          <dd>{spell.classes.map((c) => c.name).join(", ") || "None"}</dd>
        </div>
        {spell.subclasses.length > 0 && (
          <div data-testid="spell-subclasses">
            <dt>Also granted by</dt>
            <dd>
              {spell.subclasses.map((c, i) => (
                <Fragment key={c.index}>
                  {i > 0 && ", "}
                  {c.name}
                </Fragment>
              ))}
            </dd>
          </div>
        )}
      </dl>
    </article>
  );
}

// ---------------------------------------------------------------- favourites
export function FavouriteStar({
  name,
  on,
  onToggle,
  withLabel = false,
}: {
  name: string;
  on: boolean;
  onToggle: () => void;
  withLabel?: boolean;
}) {
  // A toggle button: the name stays the same and aria-pressed says whether it's starred.
  const title = on ? `${name} is a favourite. Click to unstar it.` : `Star ${name} as a favourite`;
  return (
    <button
      type="button"
      className={`star${on ? " on" : ""}${withLabel ? " btn ghost small" : ""}`}
      aria-pressed={on}
      aria-label={withLabel ? undefined : `Favourite ${name}`}
      title={title}
      data-testid="favourite-star"
      onClick={onToggle}
    >
      <span aria-hidden="true">{on ? "★" : "☆"}</span>
      {withLabel && <span>{on ? " Favourite" : " Add to favourites"}</span>}
    </button>
  );
}

// ---------------------------------------------------------------- reading a spell in place
const cache = new Map<string, Spell>();

/** Loads one spell and writes it out, for reading a spell without leaving the page. */
export function SpellReader({ index }: { index: string }) {
  const [spell, setSpell] = useState<Spell | null>(cache.get(index) ?? null);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  // Inside a scrolling list, bring the opened spell into view
  useEffect(() => {
    if (spell) box.current?.scrollIntoView?.({ block: "nearest" });
  }, [spell]);
  useEffect(() => {
    if (cache.has(index)) return;
    let current = true;
    void api.get<Spell>(`/api/rules/spells/${encodeURIComponent(index)}`).then((res) => {
      if (!current) return;
      if (res.ok) {
        cache.set(index, res.data);
        setSpell(res.data);
      } else {
        setError(res.data.error ?? "Couldn't find that spell.");
      }
    });
    return () => {
      current = false;
    };
  }, [index]);
  if (error) return <p className="field-error">{error}</p>;
  if (!spell) return <p className="muted small">Turning to the spell…</p>;
  return (
    <div className="spell-reader" data-testid="spell-reader" ref={box}>
      <SpellBlock spell={spell} heading="h4" />
    </div>
  );
}
