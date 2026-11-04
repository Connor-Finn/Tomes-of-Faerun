import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { plural } from "../../lib/bestiary";
import { dmPartyPath, longDate, playerPartyPath, PLAYER_PARTIES_PATH, type Party } from "../../lib/campaigns";
import { requestLine, type JoinRequest, type PublicParty } from "../../lib/friends";
import { useFlash } from "../../lib/flash";
import { ConfirmDialog } from "../bestiary/ConfirmDialog";
import { Avatar } from "./Friends";

// ================================================================ Player: Find a party
/** Player Mode › Campaigns › Find a party: public parties anyone can ask to join. */
export function FindParty() {
  const { flash } = useFlash();
  const [query, setQuery] = useState("");
  const [parties, setParties] = useState<PublicParty[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState<PublicParty | null>(null);
  const [note, setNote] = useState("");

  const load = useCallback(async (q: string) => {
    const res = await api.get<{ parties: PublicParty[] }>(`/api/parties/public?q=${encodeURIComponent(q.trim())}`);
    if (res.ok) setParties(res.data.parties);
    else setError(res.data.error ?? "Couldn't search the notice board.");
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(query), 200);
    return () => window.clearTimeout(timer);
  }, [query, load]);

  async function withdraw(p: PublicParty) {
    const res = await api.delete<{ message: string }>(`/api/parties/${p.id}/requests/${p.request_id}`);
    if (res.ok) flash("info", res.data.message);
    else flash("error", res.data.error ?? "That didn't work.");
    void load(query);
  }

  function standing(p: PublicParty) {
    switch (p.standing) {
      case "member":
        return (
          <Link to={playerPartyPath(p.id)} className="btn ghost small">
            You're in this party
          </Link>
        );
      case "invited":
        return (
          <Link to={PLAYER_PARTIES_PATH} className="btn primary small">
            You're invited: answer it
          </Link>
        );
      case "requested":
        return (
          <>
            <span className="pill" data-testid="standing">
              Request sent
            </span>
            <button type="button" className="btn ghost small" aria-label={`Withdraw your request to join ${p.name}`} onClick={() => withdraw(p)}>
              Withdraw
            </button>
          </>
        );
      default:
        return p.full ? (
          <span className="pill" data-testid="standing">
            Full
          </span>
        ) : (
          <button
            type="button"
            className="btn primary small"
            aria-label={`Ask to join ${p.name}`}
            onClick={() => {
              setNote("");
              setAsking(p);
            }}
          >
            Ask to join
          </button>
        );
    }
  }

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Find a party
      </h2>
      <p className="page-summary">
        The notice board of public parties. Ask to join one and its Dungeon Master decides; once they say yes, you're
        in.
      </p>
      <form className="row wrap inline-form" role="search" aria-label="Search public parties" onSubmit={(e) => e.preventDefault()}>
        <div className="field grow">
          <label htmlFor="party-search">Search by party, description or Dungeon Master</label>
          <input id="party-search" type="search" value={query} autoComplete="off" onChange={(e) => setQuery(e.target.value)} />
        </div>
      </form>

      {error && (
        <p className="form-error-summary" role="alert">
          {error}
        </p>
      )}
      {!parties && !error && <p className="muted">Reading the notice board…</p>}
      {parties?.length === 0 && (
        <div className="empty-page" data-testid="no-public-parties">
          <p>{query ? "No public party matches." : "No public parties are looking for players right now."}</p>
        </div>
      )}
      {parties && parties.length > 0 && (
        <ul className="collection-list notice-board" data-testid="public-parties">
          {parties.map((p) => (
            <li key={p.id} className="collection-card notice" data-testid="public-party">
              <h3 className="collection-name">{p.name}</h3>
              <p className="muted small" data-testid="party-facts">
                Led by {p.dm.name} · {plural(p.member_count, "player")}
                {p.campaigns.length > 0 && ` · playing ${p.campaigns.map((c) => c.name).join(", ")}`}
              </p>
              {p.description && <p className="small">{p.description}</p>}
              <div className="row wrap">{standing(p)}</div>
            </li>
          ))}
        </ul>
      )}

      {asking && (
        <ConfirmDialog
          title={`Ask to join ${asking.name}?`}
          confirmLabel="Send request"
          cancelLabel="Not now"
          tone="primary"
          onClose={() => setAsking(null)}
          onConfirm={async () => {
            const res = await api.post<{ message: string }>(`/api/parties/${asking.id}/requests`, { message: note });
            if (!res.ok) return res.data.errors?.message ?? res.data.error ?? "Your request wasn't sent.";
            flash("success", res.data.message);
            void load(query);
          }}
        >
          <p>{asking.dm.name} leads this party and will decide. You join as soon as they say yes.</p>
          <div className="field">
            <label htmlFor="join-note">A note for the Dungeon Master (optional)</label>
            <textarea
              id="join-note"
              rows={3}
              maxLength={300}
              value={note}
              placeholder="I play a halfling bard and I'm free on Fridays."
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
        </ConfirmDialog>
      )}
    </section>
  );
}

// ================================================================ DM: Join requests
/** One request with the DM's yes and no. Shared by the Join requests page and each party's page. */
export function RequestCard({
  request,
  showParty,
  onAnswered,
}: {
  request: JoinRequest;
  showParty: boolean;
  onAnswered: (party?: Party) => void;
}) {
  const { flash } = useFlash();
  const [busy, setBusy] = useState(false);
  const r = request;

  async function answer(yes: boolean) {
    setBusy(true);
    const url = `/api/parties/${r.party.id}/requests/${r.id}`;
    const res = yes ? await api.post<{ message: string; party: Party }>(`${url}/accept`) : await api.delete<{ message: string; party: Party }>(url);
    setBusy(false);
    if (!res.ok) {
      flash("error", res.data.error ?? "That didn't work.");
      return onAnswered();
    }
    flash(yes ? "success" : "info", res.data.message);
    onAnswered(res.data.party);
  }

  return (
    <li className="person request" data-testid="join-request">
      <Avatar person={r.person} />
      <div className="grow">
        <p className="member-name">{requestLine(r)}</p>
        <p className="muted small">
          {showParty && (
            <>
              <Link to={dmPartyPath(r.party.id)}>{r.party.name}</Link> ·{" "}
            </>
          )}
          {longDate(r.created_at)}
          {r.suggested_by && " · they get an invitation if you say yes"}
        </p>
        {r.message && <blockquote className="request-note">“{r.message}”</blockquote>}
      </div>
      <span className="row">
        <button type="button" className="btn primary small" disabled={busy} aria-label={`Accept ${r.person.name}`} onClick={() => answer(true)}>
          {r.suggested_by ? "Invite" : "Accept"}
        </button>
        <button type="button" className="btn ghost small" disabled={busy} aria-label={`Decline ${r.person.name}`} onClick={() => answer(false)}>
          Decline
        </button>
      </span>
    </li>
  );
}

/** DM Mode › Campaigns › Join requests: everyone waiting to join one of your parties. */
export function JoinRequests() {
  const [requests, setRequests] = useState<JoinRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    const res = await api.get<{ requests: JoinRequest[] }>("/api/parties/requests");
    if (res.ok) setRequests(res.data.requests);
    else setError(res.data.error ?? "Couldn't load your join requests.");
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Join requests
      </h2>
      <p className="page-summary">
        Players asking to join your public parties, and friends your players suggested. Nobody joins until you say
        yes. Turn on party emails in your profile to hear about new requests.
      </p>
      {error && (
        <p className="form-error-summary" role="alert">
          {error}
        </p>
      )}
      {requests?.length === 0 && (
        <div className="empty-page" data-testid="no-requests">
          <p>Nobody is waiting. Make a party public so players can find it, or let your players suggest friends.</p>
        </div>
      )}
      {requests && requests.length > 0 && (
        <ul className="person-list" data-testid="request-list">
          {requests.map((r) => (
            <RequestCard key={r.id} request={r} showParty onAnswered={() => void load()} />
          ))}
        </ul>
      )}
    </section>
  );
}
