/**
 * Favourites (starred spells, starred items...): one shared list per catalogue for the whole app,
 * so a star clicked in the builder shows in the catalogue too. Each list is kept per user, so
 * logging in as someone else never shows the last person's stars.
 *
 * The API shape is the same for every catalogue:
 *   GET    <base>/favourites           -> { favourites: [{ index, ... }] }
 *   PUT    <base>/favourites/<index>   star it
 *   DELETE <base>/favourites/<index>   unstar it
 */
import { useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";

export interface FavouriteToggle {
  ok: boolean;
  message?: string;
  error?: string;
}

export function createFavourites(base: string) {
  let favourites: Set<string> | null = null;
  let owner: number | null = null;
  let loading: Promise<void> | null = null;
  const listeners = new Set<() => void>();

  function publish(next: Set<string>) {
    favourites = next;
    listeners.forEach((l) => l());
  }

  function load(userId: number): Promise<void> {
    if (owner !== userId) {
      favourites = null;
      owner = userId;
      loading = null;
    }
    loading ??= api.get<{ favourites: { index: string }[] }>(`${base}/favourites`).then((res) => {
      if (res.ok) publish(new Set(res.data.favourites.map((s) => s.index)));
      loading = null;
    });
    return loading;
  }

  /** Your favourites, and a function to star or unstar one. */
  return function useFavourites() {
    const { user } = useAuth();
    const userId = user?.id ?? null;
    const [, rerender] = useState(0);
    useEffect(() => {
      const listener = () => rerender((n) => n + 1);
      listeners.add(listener);
      if (userId !== null && (!favourites || owner !== userId)) void load(userId);
      return () => {
        listeners.delete(listener);
      };
    }, [userId]);

    async function toggle(index: string): Promise<FavouriteToggle> {
      const current = favourites ?? new Set<string>();
      const on = !current.has(index);
      const next = new Set(current);
      if (on) next.add(index);
      else next.delete(index);
      publish(next); // star straight away; put it back if the server says no
      const url = `${base}/favourites/${encodeURIComponent(index)}`;
      const res = on ? await api.put<{ message: string }>(url) : await api.delete<{ message: string }>(url);
      if (!res.ok) {
        publish(current);
        return { ok: false, error: res.data.error ?? "Couldn't change your favourites." };
      }
      return { ok: true, message: res.data.message };
    }

    const mine = owner === userId ? favourites : null;
    return { favourites: mine, isFavourite: (index: string) => Boolean(mine?.has(index)), toggle };
  };
}
