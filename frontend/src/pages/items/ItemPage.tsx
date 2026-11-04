import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../../lib/api";
import { characterPath } from "../../lib/characters";
import { useFlash } from "../../lib/flash";
import { ITEMS_PATH, useFavouriteItems, type ItemDetail } from "../../lib/items";
import { FavouriteStar } from "../spells/SpellText";
import { ItemBlock } from "./ItemText";

/** One item: its full description, the favourite star, and which of your characters carry it. */
export function ItemPage({ index }: { index: string }) {
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "";
  const { flash } = useFlash();
  const { favourites, isFavourite, toggle } = useFavouriteItems();
  const [detail, setDetail] = useState<ItemDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "missing">("loading");

  useEffect(() => {
    setStatus("loading");
    let current = true;
    void api.get<ItemDetail>(`/api/items/${encodeURIComponent(index)}`).then((res) => {
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
    <Link to={`${ITEMS_PATH}${from}`} className="back-link">
      ← Back to the items
    </Link>
  );

  if (status === "missing") {
    return (
      <section aria-labelledby="page-title" data-testid="item-missing">
        {back}
        <h2 id="page-title" className="page-title">
          No such item
        </h2>
        <p className="muted">This page of the tome is blank. The item may be spelled differently.</p>
      </section>
    );
  }
  if (!detail || detail.item.index !== index) return <p className="muted">Turning to the item…</p>;

  const { item, kind } = detail;
  const on = favourites ? isFavourite(item.index) : detail.favourite;

  async function star() {
    const res = await toggle(item.index);
    if (res.ok) flash("success", res.message ?? "Saved.");
    else flash("error", res.error ?? "Couldn't change your favourites.");
  }

  return (
    <section>
      {back}
      <ItemBlock item={item} kind={kind} actions={<FavouriteStar name={item.name} on={on} onToggle={star} withLabel />} />
      <aside className="save-panel" aria-labelledby="carried-by-heading" data-testid="carried-by">
        <h3 id="carried-by-heading" className="leaf-heading">
          In your characters' packs
        </h3>
        {detail.characters.length > 0 ? (
          <ul className="saved-in">
            {detail.characters.map((c) => (
              <li key={c.id}>
                <Link to={characterPath(c.id, "inventory")}>{c.name}</Link>{" "}
                <span className="muted small">
                  {c.quantity > 1 ? `${c.quantity} carried` : "carried"}
                  {c.added ? ", added by you" : ""}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small">None of your characters carries one yet.</p>
        )}
        <p className="muted small">Players add items to their characters in the Character Manager, on the builder's Equipment page.</p>
      </aside>
    </section>
  );
}
