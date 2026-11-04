import { useEffect, useId, useRef, useState } from "react";
import { api } from "../../lib/api";
import type { BuildMode, Sheet } from "../../lib/characters";
import { useFavouriteItems, type ItemKind, type ItemResults, type ItemSummary } from "../../lib/items";
import { Help } from "../characters/builderParts";
import { FavouriteStar } from "../spells/SpellText";
import { ItemReader } from "./ItemText";

const SHOWN = 20;
const MAX_QUANTITY = 999;

/**
 * The player's view of the items catalogue, on the builder's Equipment page: search every SRD
 * item, read it in place, and add it to the character on top of the starting kit.
 *
 * Added items are stored in the build as { index: quantity }; the server checks them like any
 * other choice and the sheet marks them as added.
 */
export function ItemPicker({
  items,
  inventory,
  mode,
  onChange,
}: {
  items: Record<string, number>;
  inventory: Sheet["inventory"];
  mode: BuildMode;
  onChange: (items: Record<string, number>) => void;
}) {
  const { isFavourite, toggle: toggleFavourite } = useFavouriteItems();
  const [query, setQuery] = useState("");
  // Easy build starts on ordinary gear: magic items are usually handed out by the DM
  const [kind, setKind] = useState<"" | ItemKind>(mode === "easy" ? "equipment" : "");
  const [onlyFavourites, setOnlyFavourites] = useState(false);
  const [results, setResults] = useState<ItemResults | null>(null);
  const [reading, setReading] = useState<string | null>(null);
  const known = useRef(new Map<string, { name: string; kind: ItemKind }>());
  const searchId = useId();
  const kindId = useId();

  for (const i of inventory) known.current.set(i.index, { name: i.name, kind: i.kind });

  // Favourites first: ask for the matching favourites as well as the page of everything
  const [starred, setStarred] = useState<ItemSummary[]>([]);
  useEffect(() => {
    const url = new URLSearchParams({ per_page: String(SHOWN) });
    if (query.trim()) url.set("q", query.trim());
    if (kind) url.set("kind", kind);
    const favUrl = new URLSearchParams(url);
    favUrl.set("favourites", "1");
    let current = true;
    const timer = window.setTimeout(() => {
      void api.get<ItemResults>(`/api/items?${onlyFavourites ? favUrl : url}`).then((res) => {
        if (current && res.ok) setResults(res.data);
      });
      void api.get<ItemResults>(`/api/items?${favUrl}`).then((res) => {
        if (current && res.ok) setStarred(res.data.results);
      });
    }, 200);
    return () => {
      current = false;
      window.clearTimeout(timer);
    };
  }, [query, kind, onlyFavourites]);

  function add(item: ItemSummary) {
    known.current.set(item.index, { name: item.name, kind: item.kind });
    onChange({ ...items, [item.index]: Math.min((items[item.index] ?? 0) + 1, MAX_QUANTITY) });
  }
  function setQuantity(index: string, qty: number) {
    if (!Number.isFinite(qty) || qty < 1) return;
    onChange({ ...items, [index]: Math.min(Math.floor(qty), MAX_QUANTITY) });
  }
  function remove(index: string) {
    const next = { ...items };
    delete next[index];
    onChange(next);
  }

  const added = Object.entries(items);
  // Stars clicked here count straight away; the server's list fills in the rest
  const page = results?.results ?? [];
  const pool = new Map([...starred, ...page].map((i) => [i.index, i]));
  const shown = onlyFavourites
    ? page.filter((i) => isFavourite(i.index))
    : [...[...pool.values()].filter((i) => isFavourite(i.index)).sort((a, b) => a.name.localeCompare(b.name)), ...page.filter((i) => !isFavourite(i.index))].slice(0, SHOWN);
  const nameOf = (index: string) => known.current.get(index)?.name ?? index.replace(/-/g, " ");

  return (
    <fieldset className="slot spell-slot item-picker" data-testid="item-picker">
      <legend>Extra items</legend>
      <Help
        mode={mode}
        label="About extra items"
        text="Anything else your character carries: a trinket, gear you bought, or a magic item your Dungeon Master gave you. Your starting equipment above stays as the rules give it; these are marked as added on your sheet."
      />
      <ul className="picked-spells" aria-label="Extra items added" data-testid="added-items">
        {added.length === 0 && <li className="muted small">Nothing added yet.</li>}
        {added.map(([index, qty]) => (
          <li key={index} data-testid="added-item">
            <span>{nameOf(index)}</span>
            <span className="row">
              <label className="sr-only" htmlFor={`qty-${index}`}>
                How many {nameOf(index)}
              </label>
              <input
                id={`qty-${index}`}
                className="qty-input"
                type="number"
                min={1}
                max={MAX_QUANTITY}
                value={qty}
                onChange={(e) => setQuantity(index, Number(e.target.value))}
              />
              <button type="button" className="btn ghost small" onClick={() => remove(index)}>
                Remove<span className="sr-only"> {nameOf(index)}</span>
              </button>
            </span>
          </li>
        ))}
      </ul>
      <div className="catalogue-filters">
        <div className="field">
          <label htmlFor={searchId}>Search items</label>
          <input id={searchId} type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Rope, potion of healing…" />
        </div>
        <div className="field">
          <label htmlFor={kindId}>Kind of item</label>
          <select id={kindId} value={kind} onChange={(e) => setKind(e.target.value as "" | ItemKind)}>
            <option value="">Everything</option>
            <option value="equipment">Equipment</option>
            <option value="magic">Magic items</option>
          </select>
        </div>
        <label className="check">
          <input type="checkbox" checked={onlyFavourites} onChange={(e) => setOnlyFavourites(e.target.checked)} />
          Only my favourites
        </label>
      </div>
      <ul className="catalogue" aria-label="Items catalogue" data-testid="item-catalogue">
        {shown.map((i) => (
          <li key={i.index} data-testid="catalogue-item">
            <FavouriteStar name={i.name} on={isFavourite(i.index)} onToggle={() => void toggleFavourite(i.index)} />
            <span className="spell-name">{i.name}</span>
            <span className="muted small">
              {i.type} · {i.kind === "magic" ? i.rarity : i.cost ?? "no cost"}
            </span>
            <span className="catalogue-actions">
              <button
                type="button"
                className="btn ghost small"
                aria-expanded={reading === i.index}
                onClick={() => setReading((r) => (r === i.index ? null : i.index))}
              >
                {reading === i.index ? "Close" : "Read"}
                <span className="sr-only"> {i.name}</span>
              </button>
              <button type="button" className="btn ghost small" onClick={() => add(i)}>
                Add<span className="sr-only"> {i.name}</span>
              </button>
            </span>
            {reading === i.index && <ItemReader index={i.index} kind={i.kind} />}
          </li>
        ))}
        {results && results.count === 0 && (
          <li className="muted">{onlyFavourites ? "None of your favourites match. Star items with ☆ to keep them handy." : "No items match."}</li>
        )}
        {results && results.count > SHOWN && (
          <li className="muted small">…and {results.count - SHOWN} more. Search to narrow the list.</li>
        )}
      </ul>
    </fieldset>
  );
}
