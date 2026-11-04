import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { plural } from "../../lib/bestiary";
import { longDate, type Person } from "../../lib/campaigns";
import type { FriendLists, PersonResult, Relation } from "../../lib/friends";
import { useFlash } from "../../lib/flash";
import { ConfirmDialog } from "../bestiary/ConfirmDialog";

/** A round avatar, or the person's initial when they haven't uploaded one. */
export function Avatar({ person }: { person: Person }) {
  return person.avatar_url ? (
    <img className="person-avatar" src={person.avatar_url} alt="" />
  ) : (
    <span className="person-avatar initial" aria-hidden="true">
      {person.name.slice(0, 1).toUpperCase()}
    </span>
  );
}

/** Player Mode › Campaigns › Friends: find other adventurers, answer friend requests, and see your friends. */
export function Friends() {
  const { flash } = useFlash();
  const [lists, setLists] = useState<FriendLists | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PersonResult[] | null>(null);
  const [unfriending, setUnfriending] = useState<Person | null>(null);

  const load = useCallback(async () => {
    const res = await api.get<FriendLists>("/api/friends");
    if (res.ok) setLists(res.data);
    else setError(res.data.error ?? "Couldn't load your friends.");
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  // Search as you type, a moment after the typing stops.
  const search = useCallback(async (q: string) => {
    if (q.trim().length < 2) {
      setResults(null);
      return;
    }
    const res = await api.get<{ people: PersonResult[] }>(`/api/people?q=${encodeURIComponent(q.trim())}`);
    if (res.ok) setResults(res.data.people);
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void search(query), 250);
    return () => window.clearTimeout(timer);
  }, [query, search]);

  /** After any change, refresh both the lists and the search results so every button tells the truth. */
  async function act(call: Promise<{ ok: boolean; data: { message?: string; error?: string } }>, tone: "success" | "info") {
    const res = await call;
    if (res.ok) flash(tone, res.data.message ?? "Done.");
    else flash("error", res.data.error ?? "That didn't work.");
    await Promise.all([load(), search(query)]);
  }
  const befriend = (p: Person) => act(api.post("/api/friends", { user_id: p.id }), "success");
  const accept = (p: Person) => act(api.post(`/api/friends/${p.id}/accept`), "success");
  const drop = (p: Person) => act(api.delete(`/api/friends/${p.id}`), "info");

  function resultAction(p: PersonResult) {
    const by: Record<Exclude<Relation, null>, JSX.Element> = {
      friend: <span className="pill status-active">Friends</span>,
      sent: <span className="pill">Request sent</span>,
      received: (
        <button type="button" className="btn primary small" aria-label={`Accept ${p.name}'s friend request`} onClick={() => accept(p)}>
          Accept request
        </button>
      ),
    };
    if (p.relation) return by[p.relation];
    return (
      <button type="button" className="btn primary small" aria-label={`Add ${p.name} as a friend`} onClick={() => befriend(p)}>
        Add friend
      </button>
    );
  }

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Friends
      </h2>
      <p className="page-summary">
        Find other adventurers by name. Your Dungeon Master can invite friends straight into a party, and you can
        suggest friends to the parties you're in.
      </p>
      {error && (
        <p className="form-error-summary" role="alert">
          {error}
        </p>
      )}

      <form className="row wrap inline-form" role="search" aria-label="Find adventurers" onSubmit={(e) => e.preventDefault()}>
        <div className="field grow">
          <label htmlFor="people-search">Find adventurers by name</label>
          <input
            id="people-search"
            type="search"
            value={query}
            placeholder="Mira Thorn"
            autoComplete="off"
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </form>
      {query.trim().length === 1 && <p className="hint">Type at least two letters.</p>}
      {results?.length === 0 && (
        <p className="muted" data-testid="no-people">
          No adventurer goes by that name.
        </p>
      )}
      {results && results.length > 0 && (
        <ul className="person-list" aria-label="Search results" data-testid="people-results">
          {results.map((p) => (
            <li key={p.id} className="person" data-testid="person">
              <Avatar person={p} />
              <span className="member-name">{p.name}</span>
              {resultAction(p)}
            </li>
          ))}
        </ul>
      )}

      {lists && lists.received.length > 0 && (
        <>
          <h3 className="leaf-heading">Friend requests</h3>
          <ul className="person-list" data-testid="received-requests">
            {lists.received.map((p) => (
              <li key={p.id} className="person invitation" data-testid="friend-request">
                <Avatar person={p} />
                <span className="member-name">{p.name}</span>
                <span className="muted small">asked {longDate(p.requested_at)}</span>
                <span className="row">
                  <button type="button" className="btn primary small" aria-label={`Accept ${p.name}'s friend request`} onClick={() => accept(p)}>
                    Accept
                  </button>
                  <button type="button" className="btn ghost small" aria-label={`Decline ${p.name}'s friend request`} onClick={() => drop(p)}>
                    Decline
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      <h3 className="leaf-heading">Your friends{lists && lists.friends.length > 0 ? ` (${lists.friends.length})` : ""}</h3>
      {lists?.friends.length === 0 && (
        <p className="muted" data-testid="no-friends">
          No friends yet. Search for someone above and send a friend request.
        </p>
      )}
      {lists && lists.friends.length > 0 && (
        <ul className="person-list" data-testid="friend-list">
          {lists.friends.map((p) => (
            <li key={p.id} className="person" data-testid="friend">
              <Avatar person={p} />
              <span className="member-name">{p.name}</span>
              <button type="button" className="btn ghost small" aria-label={`Remove ${p.name} from your friends`} onClick={() => setUnfriending(p)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {lists && lists.sent.length > 0 && (
        <>
          <h3 className="leaf-heading">Waiting for an answer</h3>
          <p className="muted small">{plural(lists.sent.length, "request")} you sent.</p>
          <ul className="person-list" data-testid="sent-requests">
            {lists.sent.map((p) => (
              <li key={p.id} className="person" data-testid="sent-request">
                <Avatar person={p} />
                <span className="member-name">{p.name}</span>
                <span className="muted small">sent {longDate(p.requested_at)}</span>
                <button type="button" className="btn ghost small" aria-label={`Cancel your friend request to ${p.name}`} onClick={() => drop(p)}>
                  Cancel request
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {unfriending && (
        <ConfirmDialog
          title={`Remove ${unfriending.name}?`}
          confirmLabel="Remove friend"
          onClose={() => setUnfriending(null)}
          onConfirm={async () => {
            const res = await api.delete<{ message: string }>(`/api/friends/${unfriending.id}`);
            if (!res.ok) return res.data.error ?? "That didn't work.";
            flash("info", res.data.message);
            await Promise.all([load(), search(query)]);
          }}
        >
          <p>You stop being friends. Any parties you share stay as they are, and you can send a new request later.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}
