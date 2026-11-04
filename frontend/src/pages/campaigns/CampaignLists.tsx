import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type FieldErrors } from "../../lib/api";
import { plural } from "../../lib/bestiary";
import {
  DM_PARTIES_PATH,
  PLAYER_PARTIES_PATH,
  dmCampaignPath,
  instanceLine,
  longDate,
  playerCampaignPath,
  type Campaign,
  type CampaignSummary,
} from "../../lib/campaigns";
import { useFlash } from "../../lib/flash";

interface CampaignLists {
  running: CampaignSummary[];
  playing: CampaignSummary[];
}

function useCampaigns() {
  const [lists, setLists] = useState<CampaignLists | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    void api.get<CampaignLists>("/api/campaigns").then((res) => {
      if (res.ok) setLists(res.data);
      else setError(res.data.error ?? "Couldn't load your campaigns.");
    });
  }, []);
  return { lists, error };
}

export function StatusPill({ status, label }: { status: string; label: string }) {
  return (
    <span className={`pill status-${status}`} data-testid="campaign-status">
      {label}
    </span>
  );
}

function CampaignCard({ c, href, children }: { c: CampaignSummary; href: string; children?: React.ReactNode }) {
  return (
    <li className="campaign-card" data-testid="campaign-card">
      <div className="row between wrap">
        <Link to={href} className="campaign-name">
          {c.name}
        </Link>
        <StatusPill status={c.status} label={c.status_label} />
      </div>
      {c.description && <p className="campaign-blurb">{c.description}</p>}
      <p className="muted small" data-testid="campaign-facts">
        {c.party ? `${c.party.name} · ${plural(c.player_count, "player")}` : "No party yet"} ·{" "}
        {c.last_played ? `last played ${longDate(c.last_played)}` : plural(c.session_count, "session")}
      </p>
      {children}
    </li>
  );
}

// ---------------------------------------------------------------- DM: Your campaigns
/** DM Mode › Campaigns › Your campaigns: the campaigns you run, and a form to start one. */
export function DmCampaigns() {
  const navigate = useNavigate();
  const { flash } = useFlash();
  const { lists, error } = useCampaigns();
  const [name, setName] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});

  async function create(e: FormEvent) {
    e.preventDefault();
    const res = await api.post<{ campaign: Campaign }>("/api/campaigns", { name });
    if (!res.ok) {
      setErrors(res.data.errors ?? { name: res.data.error ?? "The campaign wasn't started." });
      return;
    }
    flash("success", `${res.data.campaign.name} is ready. Write its overview, then gather a party.`, {
      afterNavigate: true,
    });
    navigate(dmCampaignPath(res.data.campaign.id));
  }

  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Your campaigns
      </h2>
      <p className="page-summary">
        Each campaign is its own tome: an overview, the party, a session log, encounters from your bestiary and your
        private notes.
      </p>

      <form className="row wrap inline-form" onSubmit={create} aria-label="Start a new campaign">
        <div className="field grow">
          <label htmlFor="new-campaign">New campaign</label>
          <input
            id="new-campaign"
            value={name}
            maxLength={80}
            placeholder="The Whispering Dead"
            aria-invalid={errors.name ? true : undefined}
            aria-describedby={errors.name ? "new-campaign-error" : undefined}
            onChange={(e) => {
              setName(e.target.value);
              setErrors({});
            }}
          />
        </div>
        <button type="submit" className="btn primary small">
          Start campaign
        </button>
      </form>
      {errors.name && (
        <p className="field-error" id="new-campaign-error" data-testid="error-name">
          {errors.name}
        </p>
      )}

      {error && (
        <p className="form-error-summary" role="alert">
          {error}
        </p>
      )}
      {!lists && !error && <p className="muted">Unrolling the maps…</p>}
      {lists?.running.length === 0 && (
        <div className="empty-page" data-testid="no-campaigns">
          <p>You aren't running any campaigns yet. Name one above to begin.</p>
        </div>
      )}
      {lists && lists.running.length > 0 && (
        <ul className="campaign-list" data-testid="campaign-list">
          {lists.running.map((c) => (
            <CampaignCard key={c.id} c={c} href={dmCampaignPath(c.id)} />
          ))}
        </ul>
      )}
      <p className="muted small">
        Players join through a party. <Link to={DM_PARTIES_PATH}>Gather a party</Link> and attach it on a campaign's
        Party page.
      </p>
    </section>
  );
}

// ---------------------------------------------------------------- Player: Current campaigns
/** Player Mode › Campaigns › Current campaigns: the campaigns your parties play in. */
export function PlayerCampaigns() {
  const { lists, error } = useCampaigns();
  return (
    <section aria-labelledby="page-title">
      <h2 id="page-title" className="page-title">
        Current campaigns
      </h2>
      <p className="page-summary">
        The campaigns your parties play in, with the character you brought to each. A character in a campaign is its
        own copy: it levels up there, and your character in the Character Manager stays as it is.
      </p>
      {error && (
        <p className="form-error-summary" role="alert">
          {error}
        </p>
      )}
      {!lists && !error && <p className="muted">Unrolling the maps…</p>}
      {lists?.playing.length === 0 && (
        <div className="empty-page" data-testid="no-campaigns">
          <p>
            You aren't in any campaigns yet. When a Dungeon Master invites you to a party, accept on the Parties page,
            and their campaigns appear here.
          </p>
          <Link to={PLAYER_PARTIES_PATH} className="btn ghost">
            See your parties
          </Link>
        </div>
      )}
      {lists && lists.playing.length > 0 && (
        <ul className="campaign-list" data-testid="campaign-list">
          {lists.playing.map((c) => (
            <CampaignCard key={c.id} c={c} href={playerCampaignPath(c.id)}>
              <p className="small" data-testid="campaign-dm">
                Dungeon Master: {c.dm.name}
              </p>
              {c.my_instance ? (
                <p className="small" data-testid="my-character">
                  Playing{" "}
                  <Link to={playerCampaignPath(c.id, "character")}>
                    <strong>{c.my_instance.name}</strong>
                  </Link>
                  , {instanceLine(c.my_instance)} · {c.my_instance.current_hp}/{c.my_instance.max_hp} HP
                </p>
              ) : (
                <p className="small" data-testid="my-character">
                  <Link to={playerCampaignPath(c.id, "character")}>Bring a character</Link>
                </p>
              )}
            </CampaignCard>
          ))}
        </ul>
      )}
    </section>
  );
}
