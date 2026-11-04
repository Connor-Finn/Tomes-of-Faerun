import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../../lib/api";
import { characterPath } from "../../lib/characters";
import { useFlash } from "../../lib/flash";
import { SPELLS_PATH, useFavouriteSpells, type SpellDetail } from "../../lib/spells";
import { FavouriteStar, SpellBlock } from "./SpellText";

/** One spell: its full rules text, the favourite star, and which of your characters know it. */
export function SpellPage({ index }: { index: string }) {
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "";
  const { flash } = useFlash();
  const { favourites, isFavourite, toggle } = useFavouriteSpells();
  const [detail, setDetail] = useState<SpellDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "missing">("loading");

  useEffect(() => {
    setStatus("loading");
    let current = true;
    void api.get<SpellDetail>(`/api/spells/${encodeURIComponent(index)}`).then((res) => {
      if (!current) return;
      if (res.ok) {
        setDetail(res.data);
        setStatus("ok");
      } else {
        setStatus("missing");
      }
    });
    return () => {
      current = false;
    };
  }, [index]);

  const back = (
    <Link to={`${SPELLS_PATH}${from}`} className="back-link">
      ← Back to the spells
    </Link>
  );

  if (status === "missing") {
    return (
      <section aria-labelledby="page-title" data-testid="spell-missing">
        {back}
        <h2 id="page-title" className="page-title">
          No such spell
        </h2>
        <p className="muted">This page of the tome is blank. The spell may be spelled differently.</p>
      </section>
    );
  }
  if (!detail) return <p className="muted">Turning to the spell…</p>;

  const { spell } = detail;
  const on = favourites ? isFavourite(spell.index) : detail.favourite;

  async function star() {
    const res = await toggle(spell.index);
    if (res.ok) flash("success", res.message ?? "Saved.");
    else flash("error", res.error ?? "Couldn't change your favourites.");
  }

  return (
    <section>
      {back}
      <SpellBlock spell={spell} actions={<FavouriteStar name={spell.name} on={on} onToggle={star} withLabel />} />
      <aside className="save-panel" aria-labelledby="known-by-heading" data-testid="known-by">
        <h3 id="known-by-heading" className="leaf-heading">
          In your characters' spellbooks
        </h3>
        {detail.characters.length > 0 ? (
          <ul className="saved-in">
            {detail.characters.map((c) => (
              <li key={c.id}>
                <Link to={characterPath(c.id, "spellbook")}>{c.name}</Link>{" "}
                <span className="muted small">{c.sources.join(", ")}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small">None of your characters has learned it yet.</p>
        )}
        <p className="muted small">
          Characters learn spells in the Character Manager, where the rules decide which spells each class may take.
        </p>
      </aside>
    </section>
  );
}
