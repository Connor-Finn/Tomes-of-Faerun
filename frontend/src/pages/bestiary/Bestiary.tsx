import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import {
  capitalise,
  monsterPath,
  plural,
  type Environment,
  type MonsterPage as MonsterResults,
  type Option,
} from "../../lib/bestiary";
import { MonsterPage } from "./MonsterPage";

/** Browse Tomes › Bestiary: every SRD monster, or one monster's page when the URL names it. */
export function Bestiary() {
  const { sub } = useParams();
  return sub ? <MonsterPage index={sub} /> : <MonsterList />;
}

const PER_PAGE = 25;
const FILTERS = ["q", "type", "size", "cr_min", "cr_max", "environment", "sort"] as const;

let facetCache: MonsterResults["facets"] | null = null;

function MonsterList() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const [results, setResults] = useState<MonsterResults | null>(null);
  const [facets, setFacets] = useState(facetCache);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState(params.get("q") ?? "");

  useEffect(() => {
    void api.get<{ environments: Environment[] }>("/api/bestiary/environments").then((res) => {
      if (res.ok) setEnvironments(res.data.environments);
    });
  }, []);

  // Keep the search box in step with the URL (e.g. after Back)
  const q = params.get("q") ?? "";
  useEffect(() => setSearch(q), [q]);

  // Search as you type, a moment after the typing stops
  useEffect(() => {
    if (search === q) return;
    const timer = window.setTimeout(() => update({ q: search }), 300);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const query = params.toString();
  useEffect(() => {
    const url = new URLSearchParams(query);
    url.set("per_page", String(PER_PAGE));
    if (!facetCache) url.set("facets", "1");
    let current = true;
    void api.get<MonsterResults>(`/api/bestiary/monsters?${url}`).then((res) => {
      if (!current) return;
      if (res.ok) {
        setResults(res.data);
        setError(null);
        if (res.data.facets) {
          facetCache = res.data.facets;
          setFacets(res.data.facets);
        }
      } else {
        setError(res.data.error ?? "Couldn't open the bestiary.");
      }
    });
    return () => {
      current = false;
    };
  }, [query]);

  /** Change some filters; any change but turning the page goes back to page 1. */
  function update(changes: Partial<Record<(typeof FILTERS)[number] | "page", string>>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next, { replace: "q" in changes });
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    update({ q: search });
  }

  const filtered = FILTERS.some((f) => f !== "sort" && params.get(f));
  const narrowed = FILTERS.some((f) => f !== "sort" && f !== "environment" && params.get(f));
  const environmentName = environments.find((e) => String(e.id) === params.get("environment"))?.name;

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Bestiary
      </h2>
      <p className="page-summary">Every monster in the System Reference Document. Open one to read its stat block.</p>

      <form role="search" aria-label="Search the bestiary" className="bestiary-filters" onSubmit={onSubmit}>
        <div className="field wide">
          <label htmlFor="monster-search">Search by name</label>
          <input
            id="monster-search"
            type="search"
            value={search}
            placeholder="Goblin, dragon, lich…"
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <FilterSelect label="Creature type" value={params.get("type")} options={facets?.type} onChange={(type) => update({ type })} />
        <FilterSelect label="Size" value={params.get("size")} options={facets?.size} onChange={(size) => update({ size })} />
        <FilterSelect label="Lowest CR" value={params.get("cr_min")} options={facets?.cr} anyLabel="Any" onChange={(cr_min) => update({ cr_min })} />
        <FilterSelect label="Highest CR" value={params.get("cr_max")} options={facets?.cr} anyLabel="Any" onChange={(cr_max) => update({ cr_max })} />
        <FilterSelect
          label="My environment"
          value={params.get("environment")}
          options={environments.map((e) => ({ value: String(e.id), label: e.name }))}
          anyLabel="Anywhere"
          onChange={(environment) => update({ environment })}
        />
        <div className="field">
          <label htmlFor="monster-sort">Sort by</label>
          <select id="monster-sort" value={params.get("sort") ?? "name"} onChange={(e) => update({ sort: e.target.value === "name" ? "" : e.target.value })}>
            <option value="name">Name</option>
            <option value="cr">Challenge rating</option>
          </select>
        </div>
        <button type="submit" className="sr-only">
          Search
        </button>
      </form>

      <div className="row between wrap bestiary-status">
        <p className="muted" data-testid="monster-count" aria-live="polite">
          {results
            ? `${plural(results.count, "monster")}${environmentName ? ` in ${environmentName}` : ""}`
            : "Turning the pages…"}
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
        <div className="empty-page" data-testid="no-monsters">
          {environmentName && !narrowed
            ? `Nothing lives in ${environmentName} yet. Open a monster and tick “${environmentName}” to add it.`
            : "No monster in the tome matches that. Try fewer filters."}
        </div>
      )}
      {results && results.count > 0 && (
        <div className="table-wrap">
          <table className="monster-table" data-testid="monster-table">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">CR</th>
                <th scope="col">Creature</th>
                <th scope="col" className="num">
                  AC
                </th>
                <th scope="col" className="num">
                  HP
                </th>
              </tr>
            </thead>
            <tbody>
              {results.results.map((m) => (
                <tr key={m.index} data-testid="monster-row">
                  <td>
                    <Link to={monsterPath(m.index)} state={{ from: location.search }} className="monster-name">
                      {m.name}
                    </Link>
                  </td>
                  <td data-testid="monster-cr">{m.cr}</td>
                  <td className="muted">
                    {m.size} {m.type}
                  </td>
                  <td className="num">{m.armor_class}</td>
                  <td className="num">{m.hit_points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {results && results.pages > 1 && (
        <nav className="row between pager" aria-label="Bestiary pages">
          <button
            type="button"
            className="btn ghost small"
            disabled={results.page <= 1}
            onClick={() => update({ page: String(results.page - 1) })}
          >
            ← Previous page
          </button>
          <span className="folio" data-testid="bestiary-folio">
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

function FilterSelect({
  label,
  value,
  options,
  onChange,
  anyLabel = "All",
}: {
  label: string;
  value: string | null;
  options?: Option[];
  onChange: (value: string) => void;
  anyLabel?: string;
}) {
  const id = `filter-${label.toLowerCase().replace(/\W+/g, "-")}`;
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
