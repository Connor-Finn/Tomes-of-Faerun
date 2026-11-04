import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import { capitalise, plural, type Option } from "../../lib/bestiary";
import { useFlash } from "../../lib/flash";
import { levelLabel, spellPath, useFavouriteSpells, type SpellResults } from "../../lib/spells";
import { SpellPage } from "./SpellPage";
import { FavouriteStar } from "./SpellText";

/** Browse Tomes › Spells: every SRD spell, or one spell's page when the URL names it. */
export function Spells() {
  const { sub } = useParams();
  return sub ? <SpellPage index={sub} /> : <SpellList />;
}

const PER_PAGE = 25;
const FILTERS = ["q", "level", "school", "class", "concentration", "ritual", "favourites", "sort"] as const;
type FilterKey = (typeof FILTERS)[number];

let facetCache: SpellResults["facets"] | null = null;

function SpellList() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const { flash } = useFlash();
  const { isFavourite, toggle, favourites } = useFavouriteSpells();
  const [results, setResults] = useState<SpellResults | null>(null);
  const [facets, setFacets] = useState(facetCache);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState(params.get("q") ?? "");

  // Keep the search box in step with the URL (e.g. after Back)
  const q = params.get("q") ?? "";
  useEffect(() => setSearch(q), [q]);

  // Search as you type, a moment after the typing stops
  useEffect(() => {
    if (search === q) return;
    // Through a ref, so a filter changed while typing isn't undone by an out-of-date update
    const timer = window.setTimeout(() => latestUpdate.current({ q: search }), 300);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  // In "only my favourites", unstarring a spell takes it off the page (once the server agrees)
  const onlyFavourites = params.get("favourites") === "1";
  const [reloads, setReloads] = useState(0);

  const query = params.toString();
  useEffect(() => {
    const url = new URLSearchParams(query);
    url.set("per_page", String(PER_PAGE));
    if (!facetCache) url.set("facets", "1");
    let current = true;
    void api.get<SpellResults>(`/api/spells?${url}`).then((res) => {
      if (!current) return;
      if (res.ok) {
        setResults(res.data);
        setError(null);
        if (res.data.facets) {
          facetCache = res.data.facets;
          setFacets(res.data.facets);
        }
      } else {
        setError(res.data.error ?? "Couldn't open the spell tome.");
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

  const filtered = FILTERS.some((f) => f !== "sort" && params.get(f));
  const favouriteCount = favourites?.size ?? results?.favourite_count ?? 0;

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Spells
      </h2>
      <p className="page-summary">
        Every spell in the System Reference Document. Open one to read it, and star the ones you reach for most.
      </p>

      <form role="search" aria-label="Search the spells" className="bestiary-filters" onSubmit={onSubmit}>
        <div className="field wide">
          <label htmlFor="spell-search">Search by name</label>
          <input
            id="spell-search"
            type="search"
            value={search}
            placeholder="Fireball, cure wounds, shield…"
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <FilterSelect label="Level" value={params.get("level")} options={facets?.level} onChange={(level) => update({ level })} />
        <FilterSelect label="School" value={params.get("school")} options={facets?.school} onChange={(school) => update({ school })} />
        <FilterSelect label="Class" value={params.get("class")} options={facets?.class} onChange={(c) => update({ class: c })} />
        <FilterSelect
          label="Concentration"
          value={params.get("concentration")}
          options={[
            { value: "1", label: "Needs concentration" },
            { value: "0", label: "No concentration" },
          ]}
          anyLabel="Either"
          onChange={(concentration) => update({ concentration })}
        />
        <div className="field">
          <label htmlFor="spell-sort">Sort by</label>
          <select id="spell-sort" value={params.get("sort") ?? "name"} onChange={(e) => update({ sort: e.target.value === "name" ? "" : e.target.value })}>
            <option value="name">Name</option>
            <option value="level">Level</option>
          </select>
        </div>
        <div className="field checks">
          <label className="check">
            <input type="checkbox" checked={params.get("ritual") === "1"} onChange={(e) => update({ ritual: e.target.checked ? "1" : "" })} />
            Rituals only
          </label>
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
        <p className="muted" data-testid="spell-count" aria-live="polite">
          {results ? `${plural(results.count, "spell")}${onlyFavourites ? " starred" : ""}` : "Turning the pages…"}
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
        <div className="empty-page" data-testid="no-spells">
          {onlyFavourites && favouriteCount === 0
            ? "You haven't starred any spells yet. Tap the ☆ next to a spell to keep it here."
            : "No spell in the tome matches that. Try fewer filters."}
        </div>
      )}
      {results && results.count > 0 && (
        <div className="table-wrap">
          <table className="monster-table spell-table" data-testid="spell-table">
            <thead>
              <tr>
                <th scope="col">
                  <span className="sr-only">Favourite</span>
                </th>
                <th scope="col">Name</th>
                <th scope="col">Level</th>
                <th scope="col" className="hide-narrow">
                  School
                </th>
                <th scope="col" className="hide-narrow">
                  Casting time
                </th>
                <th scope="col" className="hide-narrow">
                  Range
                </th>
              </tr>
            </thead>
            <tbody>
              {results.results.map((s) => (
                <tr key={s.index} data-testid="spell-row">
                  <td className="star-cell">
                    <FavouriteStar name={s.name} on={favourites ? isFavourite(s.index) : Boolean(s.favourite)} onToggle={() => star(s.index)} />
                  </td>
                  <td>
                    <Link to={spellPath(s.index)} state={{ from: location.search }} className="monster-name">
                      {s.name}
                    </Link>
                    <span className="spell-flags">
                      {s.concentration && (
                        <abbr className="flag" title="Concentration">
                          C
                        </abbr>
                      )}
                      {s.ritual && (
                        <abbr className="flag" title="Ritual">
                          R
                        </abbr>
                      )}
                    </span>
                  </td>
                  <td data-testid="spell-level">{levelLabel(s.level)}</td>
                  <td className="muted hide-narrow" data-testid="spell-school">
                    {s.school}
                  </td>
                  <td className="hide-narrow">{s.casting_time}</td>
                  <td className="hide-narrow">{s.range}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {results && results.pages > 1 && (
        <nav className="row between pager" aria-label="Spell pages">
          <button
            type="button"
            className="btn ghost small"
            disabled={results.page <= 1}
            onClick={() => update({ page: String(results.page - 1) })}
          >
            ← Previous page
          </button>
          <span className="folio" data-testid="spells-folio">
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

export function FilterSelect({
  label,
  value,
  options,
  onChange,
  anyLabel = "All",
  idPrefix = "spell-filter",
}: {
  label: string;
  value: string | null;
  options?: Option[];
  onChange: (value: string) => void;
  anyLabel?: string;
  idPrefix?: string;
}) {
  const id = `${idPrefix}-${label.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        <option value="">{anyLabel}</option>
        {options?.map((o) => (
          <option key={o.value} value={o.value}>
            {capitalise(o.label)}
          </option>
        ))}
      </select>
    </div>
  );
}
