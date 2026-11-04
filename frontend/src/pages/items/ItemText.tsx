import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { itemPath, rulesUrl, type Item, type ItemKind } from "../../lib/items";
import { RulesText } from "../spells/SpellText";

/**
 * Items as they're written in the tome, shared by the DM's items catalogue, the builder's item
 * picker and a character's inventory.
 */
function stat(item: Item, kind: ItemKind): [string, ReactNode][] {
  const lines: [string, ReactNode][] = [];
  const range = (r: { normal: number; long?: number }) => (r.long ? `${r.normal}/${r.long} ft` : `${r.normal} ft`);
  if (item.cost) lines.push(["Cost", `${item.cost.quantity} ${item.cost.unit}`]);
  if (item.weight != null) lines.push(["Weight", `${item.weight} lb`]);
  if (item.quantity && item.quantity > 1) lines.push(["Sold as", `a bundle of ${item.quantity}`]);
  if (item.damage) {
    const twoHanded = item.two_handed_damage ? ` (${item.two_handed_damage.damage_dice} two-handed)` : "";
    lines.push(["Damage", `${item.damage.damage_dice} ${item.damage.damage_type.name.toLowerCase()}${twoHanded}`]);
  }
  if (item.category_range && item.range) lines.push(["Range", range(item.range)]);
  if (item.throw_range && item.category_range?.includes("Melee")) lines.push(["Thrown", range(item.throw_range)]);
  if (item.properties?.length) lines.push(["Properties", item.properties.map((p) => p.name).join(", ")]);
  if (item.armor_class) {
    const ac = item.armor_class;
    const dex = ac.dex_bonus ? (ac.max_bonus != null ? ` + Dex modifier (max ${ac.max_bonus})` : " + Dex modifier") : "";
    lines.push(["Armor Class", item.armor_category === "Shield" ? `+${ac.base}` : `${ac.base}${dex}`]);
  }
  if (item.str_minimum) lines.push(["Strength", `${item.str_minimum} or higher, or your speed drops by 10 feet`]);
  if (item.stealth_disadvantage) lines.push(["Stealth", "Disadvantage"]);
  if (item.speed) lines.push(["Speed", `${item.speed.quantity} ${item.speed.unit}`]);
  if (item.capacity) lines.push(["Carrying capacity", item.capacity]);
  if (kind === "magic" && item.variants?.length) {
    lines.push([
      "Variants",
      item.variants.map((v, i) => (
        <span key={v.index}>
          {i > 0 && ", "}
          {v.name}
        </span>
      )),
    ]);
  }
  return lines;
}

/** "Wondrous item, uncommon (requires attunement)" or "Martial melee weapon" */
export function itemLine(item: Item, kind: ItemKind): string {
  if (kind === "magic") return item.desc?.[0] ?? item.rarity?.name ?? "Magic item";
  if (item.category_range) return `${item.category_range} weapon`;
  if (item.armor_category) return item.armor_category === "Shield" ? "Shield" : `${item.armor_category} armor`;
  return item.equipment_category.name;
}

/** An item written out in full: the header lines, the stat lines and its description. */
export function ItemBlock({
  item,
  kind,
  heading = "h2",
  actions,
  linkTitle = false,
}: {
  item: Item;
  kind: ItemKind;
  heading?: "h2" | "h4";
  actions?: ReactNode;
  linkTitle?: boolean;
}) {
  const Title = heading;
  const lines = stat(item, kind);
  // A magic item's first paragraph is its type line, already shown under the name
  const text = kind === "magic" ? (item.desc ?? []).slice(1) : [...(item.desc ?? []), ...(item.special ?? [])];
  return (
    <article className={`spell-block item-block${kind === "magic" ? " magic" : ""}`} data-testid="item-block">
      <header className="row between wrap">
        <div>
          <Title id={heading === "h2" ? "page-title" : undefined} className={heading === "h2" ? "page-title" : "spell-block-title"}>
            {linkTitle ? <Link to={itemPath(item.index)}>{item.name}</Link> : item.name}
          </Title>
          <p className="creature-line" data-testid="item-line">
            {itemLine(item, kind)}
          </p>
        </div>
        {actions}
      </header>
      {lines.length > 0 && (
        <>
          <hr className="tapered" />
          <dl className="stat-lines">
            {lines.map(([label, value]) => (
              <div key={label} data-testid={`item-${label.toLowerCase().replace(/ /g, "-")}`}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
      {item.contents && item.contents.length > 0 && (
        <>
          <hr className="tapered" />
          <h4 className="rules-heading">What's inside</h4>
          <ul data-testid="item-contents">
            {item.contents.map((c) => (
              <li key={c.item.index}>
                {c.quantity} × {c.item.name}
              </li>
            ))}
          </ul>
        </>
      )}
      {text.length > 0 && (
        <>
          <hr className="tapered" />
          <div className="spell-text" data-testid="item-text">
            <RulesText paragraphs={text} />
          </div>
        </>
      )}
    </article>
  );
}

// ---------------------------------------------------------------- reading an item in place
const cache = new Map<string, Item>();

/** Loads one item and writes it out, for reading an item without leaving the page. */
export function ItemReader({ index, kind }: { index: string; kind: ItemKind }) {
  const [item, setItem] = useState<Item | null>(cache.get(index) ?? null);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (item) box.current?.scrollIntoView?.({ block: "nearest" });
  }, [item]);
  useEffect(() => {
    if (cache.has(index)) return;
    let current = true;
    void api.get<Item>(rulesUrl(kind, index)).then((res) => {
      if (!current) return;
      if (res.ok) {
        cache.set(index, res.data);
        setItem(res.data);
      } else {
        setError(res.data.error ?? "Couldn't find that item.");
      }
    });
    return () => {
      current = false;
    };
  }, [index, kind]);
  if (error) return <p className="field-error">{error}</p>;
  if (!item) return <p className="muted small">Turning to the item…</p>;
  return (
    <div className="spell-reader" data-testid="item-reader" ref={box}>
      <ItemBlock item={item} kind={kind} heading="h4" />
    </div>
  );
}
