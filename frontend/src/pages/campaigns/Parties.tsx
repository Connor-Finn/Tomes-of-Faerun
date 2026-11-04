import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type FieldErrors } from "../../lib/api";
import { plural } from "../../lib/bestiary";
import {
  DM_PARTIES_PATH,
  dmCampaignPath,
  dmPartyPath,
  longDate,
  playerCampaignPath,
  playerPartyPath,
  PLAYER_PARTIES_PATH,
  type Party,
  type PartyMember,
  type PartySummary,
} from "../../lib/campaigns";
import { useAuth } from "../../lib/auth";
import { useFlash } from "../../lib/flash";
import { ConfirmDialog } from "../bestiary/ConfirmDialog";
import { PartyChat } from "./PartyChat";

interface PartyLists {
  led: PartySummary[];
  joined: PartySummary[];
  invitations: PartySummary[];
}

function usePartyLists() {
  const [lists, setLists] = useState<PartyLists | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    const res = await api.get<PartyLists>("/api/parties");
    if (res.ok) setLists(res.data);
    else setError(res.data.error ?? "Couldn't load your parties.");
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  return { lists, error, reload: load };
}

const VISIBILITY_LABEL = { private: "Private", public: "Public" };

/** "3 unread" on a party card, when the chat has news. */
function UnreadPill({ count }: { count?: number }) {
  if (!count) return null;
  return (
    <span className="pill unread-pill" data-testid="unread">
      {count} unread
    </span>
  );
}

// ================================================================ DM: Parties
/** DM Mode › Campaigns › Parties: the parties you lead, or one of them. */
export function DmParties() {
  const { sub } = useParams();
  return sub ? <DmPartyPage id={Number(sub)} /> : <DmPartyList />;
}

function DmPartyList() {
  const navigate = useNavigate();
  const { flash } = useFlash();
  const { lists, error } = usePartyLists();
  const [name, setName] = useState("");
  const [visibility, setVisibility] = useState<"private" | "public">("private");
  const [errors, setErrors] = useState<FieldErrors>({});

  async function create(e: FormEvent) {
    e.preventDefault();
    const res = await api.post<{ party: Party }>("/api/parties", { name, visibility });
    if (!res.ok) {
      setErrors(res.data.errors ?? { name: res.data.error ?? "The party wasn't formed." });
      return;
    }
    flash("success", `${res.data.party.name} is formed. Invite your players.`, { afterNavigate: true });
    navigate(dmPartyPath(res.data.party.id));
  }

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Parties
      </h2>
      <p className="page-summary">
        Gather players into a party, then attach it to a campaign. Each player brings one of their characters.
      </p>

      <form className="row wrap inline-form" onSubmit={create} aria-label="Form a new party">
        <div className="field grow">
          <label htmlFor="new-party">New party</label>
          <input
            id="new-party"
            value={name}
            maxLength={60}
            placeholder="The Lantern Bearers"
            aria-invalid={errors.name ? true : undefined}
            onChange={(e) => {
              setName(e.target.value);
              setErrors({});
            }}
          />
        </div>
        <div className="field">
          <label htmlFor="new-party-visibility">Who can find it</label>
          <select
            id="new-party-visibility"
            value={visibility}
            onChange={(e) => setVisibility(e.target.value as "private" | "public")}
          >
            <option value="private">Private</option>
            <option value="public">Public</option>
          </select>
        </div>
        <button type="submit" className="btn primary small">
          Form party
        </button>
      </form>
      {errors.name && (
        <p className="field-error" data-testid="error-name">
          {errors.name}
        </p>
      )}
      <p className="hint">Public parties will show up in the party search when the online features arrive.</p>

      {error && (
        <p className="form-error-summary" role="alert">
          {error}
        </p>
      )}
      {lists?.led.length === 0 && (
        <div className="empty-page" data-testid="no-parties">
          <p>You don't lead any parties yet. Name one above to begin.</p>
        </div>
      )}
      {lists && lists.led.length > 0 && (
        <ul className="collection-list" data-testid="party-list">
          {lists.led.map((p) => (
            <li key={p.id} className="collection-card" data-testid="party-card">
              <div className="row wrap">
                <Link to={dmPartyPath(p.id)} className="collection-name">
                  {p.name}
                </Link>
                <UnreadPill count={p.unread} />
              </div>
              <p className="muted small" data-testid="party-facts">
                {VISIBILITY_LABEL[p.visibility]} · {plural(p.member_count, "player")}
                {p.invited_count > 0 && ` · ${p.invited_count} invited`}
              </p>
              {p.campaigns.length > 0 && (
                <p className="small">Playing {p.campaigns.map((c) => c.name).join(", ")}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function DmPartyPage({ id }: { id: number }) {
  const navigate = useNavigate();
  const { flash } = useFlash();
  const [party, setParty] = useState<Party | null>(null);
  const [missing, setMissing] = useState(false);
  const [email, setEmail] = useState("");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<PartyMember | null>(null);
  const [disbanding, setDisbanding] = useState(false);

  useEffect(() => {
    void api.get<{ party: Party }>(`/api/parties/${id}`).then((res) => {
      if (res.ok && res.data.party.role === "dm") setParty(res.data.party);
      else setMissing(true);
    });
  }, [id]);

  const back = (
    <Link to={DM_PARTIES_PATH} className="back-link">
      ← All parties
    </Link>
  );
  if (missing) {
    return (
      <section aria-labelledby="page-title" data-testid="party-missing">
        {back}
        <h2 id="page-title" className="page-title">
          Party not found
        </h2>
        <p className="muted">It may have been disbanded, or another Dungeon Master leads it.</p>
      </section>
    );
  }
  if (!party) return <p className="muted">Calling the roll…</p>;

  async function invite(e: FormEvent) {
    e.preventDefault();
    const res = await api.post<{ party: Party; message: string }>(`/api/parties/${id}/invites`, { email });
    if (!res.ok) {
      setInviteError(res.data.errors?.email ?? res.data.error ?? "The invitation wasn't sent.");
      return;
    }
    setParty(res.data.party);
    setEmail("");
    flash("success", res.data.message);
  }

  async function setVisibility(visibility: "private" | "public") {
    const res = await api.patch<{ party: Party }>(`/api/parties/${id}`, { visibility });
    if (res.ok) setParty(res.data.party);
    else flash("error", res.data.error ?? "That change wasn't saved.");
  }

  const members = party.members.filter((m) => m.status === "member");
  const invited = party.members.filter((m) => m.status === "invited");

  return (
    <section aria-labelledby="page-title" data-testid="party" className="party-page">
      {back}
      <div className="row between wrap">
        <h2 id="page-title" className="page-title">
          {party.name}
        </h2>
        <button type="button" className="btn ghost small" onClick={() => setDisbanding(true)}>
          Disband party
        </button>
      </div>
      <fieldset className="build-mode inline" data-testid="party-visibility">
        <legend>Who can find it</legend>
        {(["private", "public"] as const).map((v) => (
          <label key={v} className="check">
            <input type="radio" name="visibility" checked={party.visibility === v} onChange={() => setVisibility(v)} />
            {VISIBILITY_LABEL[v]}
          </label>
        ))}
      </fieldset>

      <PartyChat partyId={id} />

      <h3 className="leaf-heading">Players</h3>
      {members.length === 0 ? (
        <p className="muted" data-testid="no-members">
          No players yet. Invite someone below.
        </p>
      ) : (
        <ul className="member-list" data-testid="member-list">
          {members.map((m) => (
            <li key={m.id} className="member" data-testid="member">
              <span className="member-name">{m.name}</span>
              <span className="muted small">{m.email}</span>
              <span className="muted small">joined {longDate(m.joined_at!)}</span>
              <button type="button" className="btn ghost small" aria-label={`Remove ${m.name}`} onClick={() => setRemoving(m)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {invited.length > 0 && (
        <>
          <h3 className="leaf-heading">Waiting for an answer</h3>
          <ul className="member-list" data-testid="invited-list">
            {invited.map((m) => (
              <li key={m.id} className="member" data-testid="invited">
                <span className="member-name">{m.name}</span>
                <span className="muted small">{m.email}</span>
                <span className="pill">Invited</span>
                <button
                  type="button"
                  className="btn ghost small"
                  aria-label={`Cancel ${m.name}'s invitation`}
                  onClick={() => setRemoving(m)}
                >
                  Cancel invitation
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <form className="row wrap inline-form invite-form" onSubmit={invite} aria-label="Invite a player">
        <div className="field grow">
          <label htmlFor="invite-email">Invite a player by email</label>
          <input
            id="invite-email"
            type="email"
            value={email}
            placeholder="friend@example.com"
            aria-invalid={inviteError ? true : undefined}
            aria-describedby={inviteError ? "invite-error" : undefined}
            onChange={(e) => {
              setEmail(e.target.value);
              setInviteError(null);
            }}
          />
        </div>
        <button type="submit" className="btn primary small">
          Send invitation
        </button>
      </form>
      {inviteError && (
        <p className="field-error" id="invite-error" data-testid="error-email">
          {inviteError}
        </p>
      )}

      <h3 className="leaf-heading">Campaigns</h3>
      {party.campaigns.length === 0 ? (
        <p className="muted" data-testid="party-campaigns">
          Not playing any campaigns yet. Open a campaign's Party page to attach this party.
        </p>
      ) : (
        <ul className="plain-list" data-testid="party-campaigns">
          {party.campaigns.map((c) => (
            <li key={c.id}>
              <Link to={dmCampaignPath(c.id, "party")}>{c.name}</Link>
            </li>
          ))}
        </ul>
      )}

      {removing && (
        <ConfirmDialog
          title={removing.status === "member" ? `Remove ${removing.name}?` : `Cancel ${removing.name}'s invitation?`}
          confirmLabel={removing.status === "member" ? "Remove" : "Cancel invitation"}
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            const res = await api.delete<{ party: Party; message: string }>(`/api/parties/${id}/members/${removing.id}`);
            if (!res.ok) return res.data.error ?? "That didn't work.";
            setParty(res.data.party);
            flash("info", res.data.message);
          }}
        >
          <p>
            {removing.status === "member"
              ? "They leave the party and its campaigns. Their characters are kept, so nothing is lost if they come back."
              : "The invitation is withdrawn. You can invite them again later."}
          </p>
        </ConfirmDialog>
      )}
      {disbanding && (
        <ConfirmDialog
          title={`Disband ${party.name}?`}
          confirmLabel="Disband"
          onClose={() => setDisbanding(false)}
          onConfirm={async () => {
            const res = await api.delete<{ message: string }>(`/api/parties/${id}`);
            if (!res.ok) return res.data.error ?? "The party wasn't disbanded.";
            flash("info", res.data.message, { afterNavigate: true });
            navigate(DM_PARTIES_PATH);
          }}
        >
          <p>The party is gone for good. Its campaigns carry on without a party until you attach another.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}

// ================================================================ Player: Parties
/** Player Mode › Campaigns › Parties: invitations to answer and the parties you're in, or one party. */
export function PlayerParties() {
  const { sub } = useParams();
  return sub ? <PlayerPartyPage id={Number(sub)} /> : <PlayerPartyList />;
}

function PlayerPartyList() {
  const { flash } = useFlash();
  const { lists, error, reload } = usePartyLists();
  const [leaving, setLeaving] = useState<PartySummary | null>(null);
  const me = useAuth().user?.id ?? null;

  async function answer(p: PartySummary, verb: "accept" | "decline") {
    const res = await api.post<{ message: string }>(`/api/parties/${p.id}/${verb}`);
    if (res.ok) {
      flash(verb === "accept" ? "success" : "info", res.data.message);
      void reload();
    } else {
      flash("error", res.data.error ?? "That didn't work.");
    }
  }

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Parties
      </h2>
      <p className="page-summary">
        The adventuring parties you belong to. Dungeon Masters form parties and invite players. Open a party to write
        in its chat.
      </p>
      {error && (
        <p className="form-error-summary" role="alert">
          {error}
        </p>
      )}

      {lists && lists.invitations.length > 0 && (
        <>
          <h3 className="leaf-heading">Invitations</h3>
          <ul className="collection-list" data-testid="invitation-list">
            {lists.invitations.map((p) => (
              <li key={p.id} className="collection-card invitation" data-testid="invitation">
                <p className="collection-name">{p.name}</p>
                <p className="small">
                  {p.dm.name} invited you{p.invited_at ? ` on ${longDate(p.invited_at)}` : ""}.
                </p>
                {p.description && <p className="muted small">{p.description}</p>}
                <div className="row">
                  <button
                    type="button"
                    className="btn primary small"
                    aria-label={`Accept the invitation to ${p.name}`}
                    onClick={() => answer(p, "accept")}
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    className="btn ghost small"
                    aria-label={`Decline the invitation to ${p.name}`}
                    onClick={() => answer(p, "decline")}
                  >
                    Decline
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      <h3 className="leaf-heading">Your parties</h3>
      {lists?.joined.length === 0 && (
        <p className="muted" data-testid="no-parties">
          You aren't in a party yet. Ask your Dungeon Master to invite you by the email you signed up with.
        </p>
      )}
      {lists && lists.joined.length > 0 && (
        <ul className="collection-list" data-testid="party-list">
          {lists.joined.map((p) => (
            <li key={p.id} className="collection-card" data-testid="party-card">
              <div className="row wrap">
                <Link to={playerPartyPath(p.id)} className="collection-name">
                  {p.name}
                </Link>
                <UnreadPill count={p.unread} />
              </div>
              <p className="muted small" data-testid="party-facts">
                Led by {p.dm.name} · {plural(p.member_count, "player")}
              </p>
              {p.campaigns.length > 0 ? (
                <p className="small">
                  Playing{" "}
                  {p.campaigns.map((c, i) => (
                    <span key={c.id}>
                      {i > 0 && ", "}
                      <Link to={playerCampaignPath(c.id)}>{c.name}</Link>
                    </span>
                  ))}
                </p>
              ) : (
                <p className="muted small">No campaigns yet.</p>
              )}
              <div className="row wrap">
                <Link to={playerPartyPath(p.id)} className="btn primary small" aria-label={`Open ${p.name}'s chat`}>
                  Open party chat
                </Link>
                <button
                  type="button"
                  className="btn ghost small"
                  aria-label={`Leave ${p.name}`}
                  onClick={() => setLeaving(p)}
                >
                  Leave party
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {leaving && me !== null && (
        <ConfirmDialog
          title={`Leave ${leaving.name}?`}
          confirmLabel="Leave"
          onClose={() => setLeaving(null)}
          onConfirm={async () => {
            const res = await api.delete<{ message: string }>(`/api/parties/${leaving.id}/members/${me}`);
            if (!res.ok) return res.data.error ?? "You didn't leave.";
            flash("info", res.data.message);
            void reload();
          }}
        >
          <p>You leave the party and its campaigns. The Dungeon Master can invite you back later.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}

/** Player Mode › Campaigns › Parties › one party: who's in it, its chat and its campaigns. */
function PlayerPartyPage({ id }: { id: number }) {
  const navigate = useNavigate();
  const { flash } = useFlash();
  const me = useAuth().user?.id ?? null;
  const [party, setParty] = useState<Party | null>(null);
  const [missing, setMissing] = useState(false);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    void api.get<{ party: Party }>(`/api/parties/${id}`).then((res) => {
      // The DM manages their own parties from DM Mode; send them there.
      if (res.ok && res.data.party.role === "dm") navigate(dmPartyPath(id), { replace: true });
      else if (res.ok && res.data.party.members.some((m) => m.id === me && m.status === "member")) setParty(res.data.party);
      else setMissing(true);
    });
  }, [id, me, navigate]);

  const back = (
    <Link to={PLAYER_PARTIES_PATH} className="back-link">
      ← All parties
    </Link>
  );
  if (missing) {
    return (
      <section aria-labelledby="page-title" data-testid="party-missing">
        {back}
        <h2 id="page-title" className="page-title">
          Party not found
        </h2>
        <p className="muted">It may have been disbanded, or you aren't in it any more.</p>
      </section>
    );
  }
  if (!party) return <p className="muted">Calling the roll…</p>;
  const members = party.members.filter((m) => m.status === "member");

  return (
    <section aria-labelledby="page-title" data-testid="party" className="party-page">
      {back}
      <h2 id="page-title" className="page-title">
        {party.name}
      </h2>
      {party.description && <p className="page-summary">{party.description}</p>}
      <ul className="party-roster" aria-label="Who's in the party" data-testid="party-roster">
        <li>
          {party.dm.name} <span className="muted small">(Dungeon Master)</span>
        </li>
        {members.map((m) => (
          <li key={m.id}>{m.id === me ? `${m.name} (you)` : m.name}</li>
        ))}
      </ul>

      <PartyChat partyId={id} />

      <h3 className="leaf-heading">Campaigns</h3>
      {party.campaigns.length === 0 ? (
        <p className="muted" data-testid="party-campaigns">
          No campaigns yet. Your Dungeon Master attaches the party to a campaign.
        </p>
      ) : (
        <ul className="plain-list" data-testid="party-campaigns">
          {party.campaigns.map((c) => (
            <li key={c.id}>
              <Link to={playerCampaignPath(c.id)}>{c.name}</Link>
            </li>
          ))}
        </ul>
      )}
      <button type="button" className="btn ghost small" onClick={() => setLeaving(true)}>
        Leave party
      </button>

      {leaving && me !== null && (
        <ConfirmDialog
          title={`Leave ${party.name}?`}
          confirmLabel="Leave"
          onClose={() => setLeaving(false)}
          onConfirm={async () => {
            const res = await api.delete<{ message: string }>(`/api/parties/${id}/members/${me}`);
            if (!res.ok) return res.data.error ?? "You didn't leave.";
            flash("info", res.data.message, { afterNavigate: true });
            navigate(PLAYER_PARTIES_PATH);
          }}
        >
          <p>You leave the party and its campaigns. The Dungeon Master can invite you back later.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}
