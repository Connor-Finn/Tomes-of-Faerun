import { Fragment } from "react";
import { capitalise, creatureLine, modifier, signed, xp, type Monster } from "../../lib/bestiary";

/**
 * A monster's stat block, laid out the way the printed books do it.
 * Pure display: it's reused wherever a monster is shown (bestiary, and later encounters).
 */
const ABILITIES = [
  ["strength", "STR"],
  ["dexterity", "DEX"],
  ["constitution", "CON"],
  ["intelligence", "INT"],
  ["wisdom", "WIS"],
  ["charisma", "CHA"],
] as const;

type Usage = NonNullable<NonNullable<Monster["actions"]>[number]["usage"]>;

function usageLabel(u?: Usage): string {
  if (!u) return "";
  if (u.type === "per day") return ` (${u.times}/Day)`;
  if (u.type === "recharge on roll") return ` (Recharge ${u.min_value === 6 ? "6" : `${u.min_value}–6`})`;
  if (u.type === "recharge after rest") return " (Recharges after a Short or Long Rest)";
  return "";
}

function armourClass(m: Monster): string {
  return m.armor_class
    .map((ac) => {
      const why =
        ac.type === "natural" ? "natural armor" : ac.type === "armor" ? ac.armor?.map((a) => a.name.toLowerCase()).join(", ") : ac.type === "spell" ? "with spell" : ac.type === "condition" ? ac.desc : "";
      return why ? `${ac.value} (${why})` : String(ac.value);
    })
    .join(", ");
}

function speed(m: Monster): string {
  // Walking speed first, as the books print it (the API sorts the keys alphabetically)
  const order = (key: string) => (key === "walk" ? "" : key);
  return Object.entries(m.speed)
    .filter(([key]) => key !== "hover")
    .sort(([a], [b]) => order(a).localeCompare(order(b)))
    .map(([key, value]) => (key === "walk" ? String(value) : `${key} ${value}${key === "fly" && m.speed.hover ? " (hover)" : ""}`))
    .join(", ");
}

function proficiencies(m: Monster, prefix: string): string {
  return m.proficiencies
    .filter((p) => p.proficiency.name.startsWith(prefix))
    .map((p) => {
      const name = p.proficiency.name.slice(prefix.length);
      return `${prefix.startsWith("Saving") ? capitalise(name.toLowerCase()) : name} ${signed(p.value)}`;
    })
    .join(", ");
}

function senses(m: Monster): string {
  return Object.entries(m.senses)
    .map(([key, value]) => (key === "passive_perception" ? `passive Perception ${value}` : `${key} ${value}`))
    .join(", ");
}

export function StatBlock({ monster: m, cr }: { monster: Monster; cr: string }) {
  const lines: [string, string][] = [
    ["Saving Throws", proficiencies(m, "Saving Throw: ")],
    ["Skills", proficiencies(m, "Skill: ")],
    ["Damage Vulnerabilities", m.damage_vulnerabilities.join(", ")],
    ["Damage Resistances", m.damage_resistances.join(", ")],
    ["Damage Immunities", m.damage_immunities.join(", ")],
    ["Condition Immunities", m.condition_immunities.map((c) => c.name.toLowerCase()).join(", ")],
    ["Senses", senses(m)],
    ["Languages", m.languages || "—"],
    ["Challenge", `${cr} (${xp(m.xp)})`],
    ["Proficiency Bonus", signed(m.proficiency_bonus)],
  ];

  return (
    <article className="stat-block" data-testid="stat-block" aria-labelledby="page-title">
      <header>
        <h2 id="page-title" className="page-title">
          {m.name}
        </h2>
        <p className="creature-line">{capitalise(creatureLine(m))}</p>
      </header>

      <hr className="tapered" />
      <dl className="stat-lines">
        <div data-testid="monster-ac">
          <dt>Armor Class</dt>
          <dd>{armourClass(m)}</dd>
        </div>
        <div data-testid="monster-hp">
          <dt>Hit Points</dt>
          <dd>
            {m.hit_points} ({m.hit_points_roll})
          </dd>
        </div>
        <div data-testid="monster-speed">
          <dt>Speed</dt>
          <dd>{speed(m)}</dd>
        </div>
      </dl>

      <hr className="tapered" />
      <table className="monster-abilities" data-testid="monster-abilities">
        <thead>
          <tr>
            {ABILITIES.map(([, short]) => (
              <th key={short} scope="col">
                {short}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            {ABILITIES.map(([key, short]) => (
              <td key={key} data-testid={`monster-${short.toLowerCase()}`}>
                {m[key]} ({signed(modifier(m[key]))})
              </td>
            ))}
          </tr>
        </tbody>
      </table>

      <hr className="tapered" />
      <dl className="stat-lines">
        {lines
          .filter(([, value]) => value)
          .map(([label, value]) => (
            <div key={label} data-testid={`monster-${label.toLowerCase().replace(/ /g, "-")}`}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
      </dl>

      {m.desc && <p className="monster-desc">{m.desc}</p>}
      <hr className="tapered" />

      <Abilities items={m.special_abilities} testid="traits" />
      <Abilities heading="Actions" items={m.actions} testid="actions" />
      <Abilities heading="Reactions" items={m.reactions} testid="reactions" />
      <Abilities
        heading="Legendary Actions"
        items={m.legendary_actions}
        testid="legendary-actions"
        intro={`The ${m.name.toLowerCase()} can take 3 legendary actions, choosing from the options below. Only one legendary action option can be used at a time and only at the end of another creature's turn. The ${m.name.toLowerCase()} regains spent legendary actions at the start of its turn.`}
      />
    </article>
  );
}

function Abilities({
  heading,
  items,
  testid,
  intro,
}: {
  heading?: string;
  items?: { name: string; desc: string; usage?: Usage }[];
  testid: string;
  intro?: string;
}) {
  if (!items?.length) return null;
  return (
    <section className="stat-section" data-testid={`monster-${testid}`} aria-label={heading ?? "Traits"}>
      {heading && <h3 className="stat-heading">{heading}</h3>}
      {intro && <p>{intro}</p>}
      {items.map((a) => (
        <Fragment key={a.name}>
          <p>
            <strong className="ability-title">
              {a.name}
              {usageLabel(a.usage)}.
            </strong>{" "}
            {a.desc.split("\n")[0]}
          </p>
          {a.desc
            .split("\n")
            .slice(1)
            .filter(Boolean)
            .map((para, i) => (
              <p key={i} className="ability-more">
                {para}
              </p>
            ))}
        </Fragment>
      ))}
    </section>
  );
}
