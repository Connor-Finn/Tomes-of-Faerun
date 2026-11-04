import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import { plural } from "../../lib/bestiary";
import { useFlash } from "../../lib/flash";
import { itemPath, useFavouriteItems, type ItemResults } from "../../lib/items";
import { FilterSelect } from "../spells/Spells";
import { FavouriteStar } from "../spells/SpellText";
import { ItemPage } from "./ItemPage";

/** Browse Tomes › Items: every SRD item and magic item, or one item's page when the URL names it. */
export function Items() {
  const { sub } = useParams();
  return sub ? <ItemPage index={sub} /> : <ItemList />;
}

const PER_PAGE = 25;
const FILTERS = ["q", "kind", "category", "rarity", "favourites", "sort"] as const;
type FilterKey = (typeof FILTERS)[number];

let facetCache: ItemResults["facets"] | null = null;

function ItemList() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const { flash } = useFlash();
  const { isFavourite, toggle, favourites } = useFavouriteItems();
  const [results, setResults] = useState<ItemResults | null>(null);
  const [facets, setFacets] = useState(facetCache);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState(params.get("q") ?? "");

  const q = params.get("q") ?? "";
  useEffect(() => setSearch(q), [q]);

  // Search as you type, a moment after the typing stops
  useEffect(() => {
    if (search === q) return;
    const timer = window.setTimeout(() => latestUpdate.current({ q: search }), 300);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const onlyFavourites = params.get("favourites") === "1";
  const [reloads, setReloads] = useState(0);

  const query = params.toString();
  useEffect(() => {
    const url = new URLSearchParams(query);
    url.set("per_page", String(PER_PAGE));
    if (!facetCache) url.set("facets", "1");
    let current = true;
    void api.get<ItemResults>(`/api/items?${url}`).then((res) => {
      if (!current) return;
      if (res.ok) {
        setResults(res.data);
        setError(null);
        if (res.data.facets) {
          facetCache = res.data.facets;
          setFacets(res.data.facets);
        }
      } else {
        setError(res.data.error ?? "Couldn't open the items tome.");
      }
    });
    return () => {
      current = false;
    };
  }, [query, reloads]);

  /** Change some filters; any change but turning the page goes back to page 1. */
  function update(changes: Partial<Record<FilterKey | "page", string>>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next, { replace: "q" in changes });
  }

  const latestUpdate = useRef(update);
  latestUpdate.current = update;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    update({ q: search });
  }

  async function star(index: string) {
    const res = await toggle(index);
    if (!res.ok) flash("error", res.error ?? "Couldn't change your favourites.");
    else if (onlyFavourites) setReloads((n) => n + 1);
  }

  const kind = params.get("kind");
  const filtered = FILTERS.some((f) => f !== "sort" && params.get(f));
  const favouriteCount = favourites?.size ?? results?.favourite_count ?? 0;

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Items
      </h2>
      <p className="page-summary">
        Weapons, armour, adventuring gear, tools, mounts and every magic item in the System Reference Document.
      </p>

      <form role="search" aria-label="Search the items" className="bestiary-filters" onSubmit={onSubmit}>
        <div className="field wide">
          <label htmlFor="item-search">Search by name</label>
          <input
            id="item-search"
            type="search"
            value={search}
            placeholder="Longsword, bag of holding, rope…"
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <FilterSelect
          idPrefix="item-filter"
          label="Kind"
          value={kind}
          options={facets?.kind}
          anyLabel="Everything"
          // Rarity only applies to magic items, so leaving them drops it
          onChange={(k) => update({ kind: k, ...(k === "equipment" ? { rarity: "" } : {}) })}
        />
        <FilterSelect idPrefix="item-filter" label="Category" value={params.get("category")} options={facets?.category} onChange={(category) => update({ category })} />
        {kind !== "equipment" && (
          <FilterSelect idPrefix="item-filter" label="Rarity" value={params.get("rarity")} options={facets?.rarity} onChange={(rarity) => update({ rarity })} />
        )}
        <div className="field">
          <label htmlFor="item-sort">Sort by</label>
          <select id="item-sort" value={params.get("sort") ?? "name"} onChange={(e) => update({ sort: e.target.value === "name" ? "" : e.target.value })}>
            <option value="name">Name</option>
            <option value="category">Category</option>
            <option value="cost">Cost</option>
            <option value="rarity">Rarity</option>
          </select>
        </div>
        <div className="field checks">
          <label className="check">
            <input type="checkbox" checked={onlyFavourites} onChange={(e) => update({ favourites: e.target.checked ? "1" : "" })} />
            Only my favourites ({favouriteCount})
          </label>
        </div>
        <button type="submit" className="sr-only">
          Search
        </button>
      </form>

      <div className="row between wrap bestiary-status">
        <p className="muted" data-testid="item-count" aria-live="polite">
          {results ? `${plural(results.count, "item")}${onlyFavourites ? " starred" : ""}` : "Turning the pages…"}
        </p>
        {filtered && (
          <button type="button" className="link-button" onClick={() => setParams(new URLSearchParams())}>
            Clear the filters
          </button>
        )}
      </div>

      {error && (
        <p className="form-error-summary" role="alert">
          {error}
        </p>
      )}
      {results?.count === 0 && (
        <div className="empty-page" data-testid="no-items">
          {onlyFavourites && favouriteCount === 0
            ? "You haven't starred any items yet. Tap the ☆ next to an item to keep it here."
            : "No item in the tome matches that. Try fewer filters."}
        </div>
      )}
      {results && results.count > 0 && (
        <div className="table-wrap">
          <table className="monster-table item-table" data-testid="item-table">
            <thead>
              <tr>
                <th scope="col">
                  <span className="sr-only">Favourite</span>
                </th>
                <th scope="col">Name</th>
                <th scope="col">Type</th>
                <th scope="col">Cost or rarity</th>
                <th scope="col" className="hide-narrow">
                  Weight
                </th>
              </tr>
            </thead>
            <tbody>
              {results.results.map((i) => (
                <tr key={i.index} data-testid="item-row" data-kind={i.kind}>
                  <td className="star-cell">
                    <FavouriteStar name={i.name} on={favourites ? isFavourite(i.index) : Boolean(i.favourite)} onToggle={() => star(i.index)} />
                  </td>
                  <td>
                    <Link to={itemPath(i.index)} state={{ from: location.search }} className="monster-name">
                      {i.name}
                    </Link>
                    {i.attunement && (
                      <span className="spell-flags">
                        <abbr className="flag" title="Requires attunement">
                          A
                        </abbr>
                      </span>
                    )}
                  </td>
                  <td className="muted" data-testid="item-type">
                    {i.type}
                  </td>
                  <td data-testid="item-value">
                    {i.kind === "magic" ? <span className={`rarity rarity-${i.rarity?.toLowerCase().replace(/ /g, "-")}`}>{i.rarity}</span> : i.cost ?? "—"}
                  </td>
                  <td className="hide-narrow">{i.weight != null ? `${i.weight} lb` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {results && results.pages > 1 && (
        <nav className="row between pager" aria-label="Item pages">
          <button type="button" className="btn ghost small" disabled={results.page <= 1} onClick={() => update({ page: String(results.page - 1) })}>
            ← Previous page
          </button>
          <span className="folio" data-testid="items-folio">
            Leaf {results.page} of {results.pages}
          </span>
          <button
            type="button"
            className="btn ghost small"
            disabled={results.page >= results.pages}
            onClick={() => update({ page: String(results.page + 1) })}
          >
            Next page →
          </button>
        </nav>
      )}
    </section>
  );
}
