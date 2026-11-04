import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { Breadcrumbs, Tome } from "../../components/Tome";
import { api, type FieldErrors } from "../../lib/api";
import { COLLECTIONS_PATH, collectionPath, plural, xp, type CollectionSummary } from "../../lib/bestiary";
import {
  DM_CAMPAIGNS_PATH,
  DM_PARTIES_PATH,
  PLAYER_CAMPAIGNS_PATH,
  STATUSES,
  dmCampaignPath,
  dmPartyPath,
  instanceLine,
  longDate,
  playerCampaignPath,
  today,
  type Campaign,
  type CampaignStatus,
  type InstanceSummary,
  type PartySummary,
  type SessionEntry,
} from "../../lib/campaigns";
import { useFlash } from "../../lib/flash";
import { MODE_LABELS, useEnterMode, type Mode } from "../../lib/mode";
import { ConfirmDialog } from "../bestiary/ConfirmDialog";
import { PageHeading } from "../characters/CharacterTome";
import { StatusPill } from "./CampaignLists";
import { HpBar, InstanceView, PlayerCharacterPage } from "./InstancePages";

/**
 * Every campaign opens as its own tome. The DM and the players read different editions:
 * the DM's has the encounters and private notes, the players' has their own character.
 */
const DM_PAGES = [
  { slug: "overview", title: "Overview" },
  { slug: "party", title: "Party" },
  { slug: "sessions", title: "Session log" },
  { slug: "encounters", title: "Encounters" },
  { slug: "notes", title: "DM notes" },
];
const PLAYER_PAGES = [
  { slug: "overview", title: "Overview" },
  { slug: "character", title: "Your character" },
  { slug: "party", title: "Party" },
  { slug: "sessions", title: "Session log" },
];

export function CampaignTome({ mode }: { mode: Mode }) {
  const { id, page: slug, sub } = useParams();
  const campaignId = Number(id);
  useEnterMode(mode);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "missing">("loading");

  const reload = useCallback(async () => {
    const res = await api.get<{ campaign: Campaign }>(`/api/campaigns/${campaignId}`);
    if (res.ok) {
      setCampaign(res.data.campaign);
      setStatus("ready");
    } else {
      setStatus("missing");
    }
  }, [campaignId]);

  useEffect(() => {
    setStatus("loading");
    void reload();
  }, [reload]);

  const listPath = mode === "dm" ? DM_CAMPAIGNS_PATH : PLAYER_CAMPAIGNS_PATH;
  const trail = [
    { label: "Guild Hall", to: "/guild-hall" },
    { label: MODE_LABELS[mode], to: "/guild-hall" },
    { label: "Campaigns", to: listPath },
  ];

  if (!slug) return <Navigate to={(mode === "dm" ? dmCampaignPath : playerCampaignPath)(campaignId)} replace />;
  if (status === "missing") {
    return (
      <>
        <Breadcrumbs trail={[...trail, { label: "Missing" }]} />
        <div className="card narrow center" data-testid="campaign-missing">
          <h1>Campaign not found</h1>
          <p className="muted">It may have been deleted, or you aren't part of it.</p>
          <Link to={listPath} className="btn ghost">
            Back to your campaigns
          </Link>
        </div>
      </>
    );
  }
  if (!campaign) return <p className="muted center">Unrolling the map…</p>;

  // Each reader gets their own edition: a player who opens the DM's link is sent to theirs, and back.
  if (campaign.role !== mode) {
    const to = campaign.role === "dm" ? dmCampaignPath(campaign.id) : playerCampaignPath(campaign.id);
    return <Navigate to={to} replace />;
  }

  const pages = mode === "dm" ? DM_PAGES : PLAYER_PAGES;
  const page = pages.find((p) => p.slug === slug);
  const basePath = mode === "dm" ? `/dm/campaigns/c/${campaign.id}` : `/play/campaigns/c/${campaign.id}`;
  const props = { campaign, onChange: setCampaign, reload };

  return (
    <>
      <Breadcrumbs trail={[...trail, { label: campaign.name }]} />
      <Tome
        eyebrow={mode === "dm" ? "Campaign · Dungeon Master" : `Campaign · run by ${campaign.dm.name}`}
        title={campaign.name}
        subtitle={campaign.party ? `Played by ${campaign.party.name}` : "No party yet"}
        basePath={basePath}
        pages={pages}
        current={page?.slug}
        cover={mode === "dm" ? "navy" : "forest"}
        aside={<StatusPill status={campaign.status} label={campaign.status_label} />}
      >
        {!page && (
          <section aria-labelledby="page-title" data-testid="missing-page">
            <PageHeading title="This page is missing" />
            <Link to={`${basePath}/overview`} className="btn ghost small">
              Go to the overview
            </Link>
          </section>
        )}
        {mode === "dm" && page?.slug === "overview" && <DmOverview {...props} />}
        {mode === "dm" && page?.slug === "party" && !sub && <DmPartyPage {...props} />}
        {mode === "dm" && page?.slug === "party" && sub && <DmPlayerCharacter campaign={campaign} instanceId={Number(sub)} />}
        {mode === "dm" && page?.slug === "sessions" && <DmSessions {...props} />}
        {mode === "dm" && page?.slug === "encounters" && <DmEncounters {...props} />}
        {mode === "dm" && page?.slug === "notes" && <DmNotes {...props} />}
        {mode === "player" && page?.slug === "overview" && <PlayerOverview campaign={campaign} />}
        {mode === "player" && page?.slug === "character" && <PlayerCharacterPage campaign={campaign} onChange={reload} />}
        {mode === "player" && page?.slug === "party" && <PlayerPartyPage campaign={campaign} />}
        {mode === "player" && page?.slug === "sessions" && <SessionList sessions={campaign.sessions} />}
      </Tome>
    </>
  );
}

interface PageProps {
  campaign: Campaign;
  onChange: (c: Campaign) => void;
  reload: () => Promise<void>;
}

async function patchCampaign(id: number, body: Record<string, unknown>) {
  return api.patch<{ campaign: Campaign }>(`/api/campaigns/${id}`, body);
}

// ================================================================ Overview
function DmOverview({ campaign, onChange }: PageProps) {
  const { flash } = useFlash();
  const navigate = useNavigate();
  const [name, setName] = useState(campaign.name);
  const [description, setDescription] = useState(campaign.description);
  const [status, setStatus] = useState<CampaignStatus>(campaign.status);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [deleting, setDeleting] = useState(false);
  const dirty = name !== campaign.name || description !== campaign.description || status !== campaign.status;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await patchCampaign(campaign.id, { name, description, status });
    if (!res.ok) {
      setErrors(res.data.errors ?? { name: res.data.error ?? "The overview wasn't saved." });
      return;
    }
    setErrors({});
    onChange(res.data.campaign);
    flash("success", "Overview saved.");
  }

  return (
    <section aria-labelledby="page-title" data-testid="campaign-overview">
      <PageHeading title="Overview" summary="What the campaign is about. Your players read this page too." />
      <form onSubmit={onSubmit} className="notes-form" aria-label="Campaign overview">
        <div className="field">
          <label htmlFor="campaign-name">Name</label>
          <input
            id="campaign-name"
            value={name}
            maxLength={80}
            aria-invalid={errors.name ? true : undefined}
            onChange={(e) => setName(e.target.value)}
          />
          {errors.name && (
            <p className="field-error" data-testid="error-name">
              {errors.name}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor="campaign-status">Status</label>
          <select id="campaign-status" value={status} onChange={(e) => setStatus(e.target.value as CampaignStatus)}>
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="campaign-description">Setting and story</label>
          <textarea
            id="campaign-description"
            rows={7}
            maxLength={4000}
            value={description}
            placeholder="Where it's set, what's going on, and what the heroes are hoping to do…"
            onChange={(e) => setDescription(e.target.value)}
          />
          {errors.description && <p className="field-error">{errors.description}</p>}
        </div>
        <div className="row between wrap">
          <button type="button" className="btn ghost small" onClick={() => setDeleting(true)}>
            Delete campaign
          </button>
          <button type="submit" className="btn primary" disabled={!dirty}>
            Save overview
          </button>
        </div>
      </form>
      {deleting && (
        <ConfirmDialog
          title={`Delete ${campaign.name}?`}
          confirmLabel="Delete"
          onClose={() => setDeleting(false)}
          onConfirm={async () => {
            const res = await api.delete<{ message: string }>(`/api/campaigns/${campaign.id}`);
            if (!res.ok) return res.data.error ?? "The campaign wasn't deleted.";
            flash("info", res.data.message, { afterNavigate: true });
            navigate(DM_CAMPAIGNS_PATH);
          }}
        >
          <p>
            The overview, session log, notes and every player's character in this campaign are gone for good. Your
            party, your bestiary collections and the players' own characters are kept.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}

function PlayerOverview({ campaign }: { campaign: Campaign }) {
  const mine = campaign.my_instance;
  return (
    <section aria-labelledby="page-title" data-testid="campaign-overview">
      <PageHeading title="Overview" />
      <dl className="sheet-identity">
        <div>
          <dt>Dungeon Master</dt>
          <dd data-testid="overview-dm">{campaign.dm.name}</dd>
        </div>
        <div>
          <dt>Party</dt>
          <dd>{campaign.party?.name ?? "—"}</dd>
        </div>
        <div>
          <dt>Sessions</dt>
          <dd>{campaign.session_count}</dd>
        </div>
        <div>
          <dt>Last played</dt>
          <dd>{campaign.last_played ? longDate(campaign.last_played) : "Not yet"}</dd>
        </div>
      </dl>
      {campaign.description ? (
        <div className="prose" data-testid="overview-description">
          {campaign.description.split(/\n{2,}/).map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      ) : (
        <p className="muted">The Dungeon Master hasn't written an overview yet.</p>
      )}
      <div className="callout">
        {mine ? (
          <p>
            You're playing <strong>{mine.name}</strong>, {instanceLine(mine)}.{" "}
            <Link to={playerCampaignPath(campaign.id, "character")}>Open your character</Link>
          </p>
        ) : (
          <p>
            You haven't brought a character yet.{" "}
            <Link to={playerCampaignPath(campaign.id, "character")}>Choose one</Link>
          </p>
        )}
      </div>
    </section>
  );
}

// ================================================================ Party
function DmPartyPage({ campaign, onChange }: PageProps) {
  const { flash } = useFlash();
  const [parties, setParties] = useState<PartySummary[] | null>(null);
  const [choice, setChoice] = useState<string>("");

  useEffect(() => {
    void api.get<{ led: PartySummary[] }>("/api/parties").then((res) => res.ok && setParties(res.data.led));
  }, []);

  async function setParty(partyId: number | null) {
    const res = await patchCampaign(campaign.id, { party_id: partyId });
    if (!res.ok) {
      flash("error", res.data.errors?.party_id ?? res.data.error ?? "That change wasn't saved.");
      return;
    }
    onChange(res.data.campaign);
    flash(
      "success",
      partyId ? `${res.data.campaign.party?.name} is now playing ${campaign.name}.` : "The party was taken off the campaign.",
    );
  }

  const picker =
    parties && parties.length > 0 ? (
      <form
        className="row wrap inline-form"
        aria-label="Choose the party"
        onSubmit={(e) => {
          e.preventDefault();
          if (choice) void setParty(Number(choice));
        }}
      >
        <div className="field grow">
          <label htmlFor="campaign-party">{campaign.party ? "Switch to another party" : "Party"}</label>
          <select id="campaign-party" value={choice} onChange={(e) => setChoice(e.target.value)}>
            <option value="">Choose a party…</option>
            {parties
              .filter((p) => p.id !== campaign.party?.id)
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({plural(p.member_count, "player")})
                </option>
              ))}
          </select>
        </div>
        <button type="submit" className="btn primary small" disabled={!choice}>
          {campaign.party ? "Switch party" : "Attach party"}
        </button>
      </form>
    ) : parties ? (
      <p className="muted" data-testid="no-parties">
        You don't lead any parties yet. <Link to={DM_PARTIES_PATH}>Form a party</Link> and invite your players first.
      </p>
    ) : null;

  return (
    <section aria-labelledby="page-title" data-testid="campaign-party">
      <PageHeading
        title="Party"
        summary="The players in this campaign and the characters they brought. You can read their sheets and leave each one a note, but only the player changes their character."
      />
      {campaign.party ? (
        <div className="row between wrap">
          <p data-testid="attached-party">
            Played by <Link to={dmPartyPath(campaign.party.id)}>{campaign.party.name}</Link>
          </p>
          <button type="button" className="btn ghost small" onClick={() => setParty(null)}>
            Take the party off
          </button>
        </div>
      ) : (
        <p className="muted" data-testid="attached-party">
          No party is playing this campaign yet.
        </p>
      )}
      {picker}

      {campaign.party && (
        <>
          <h3 className="leaf-heading">At the table</h3>
          {campaign.players.length === 0 ? (
            <p className="muted" data-testid="no-players">
              Nobody has joined {campaign.party.name} yet. Invite players from the party's page.
            </p>
          ) : (
            <ul className="player-list" data-testid="player-list">
              {campaign.players.map((p) => {
                const inst = p.instance as InstanceSummary | null;
                return (
                  <li key={p.id} className="player-card" data-testid="player-card">
                    <p className="player-name">{p.name}</p>
                    {inst ? (
                      <>
                        <p>
                          <Link to={dmCampaignPath(campaign.id, `party/${inst.id}`)} className="character-name">
                            {inst.name}
                          </Link>{" "}
                          <span className="muted small">{instanceLine(inst)}</span>
                        </p>
                        <HpBar instance={inst} />
                        {inst.dm_note && (
                          <p className="small dm-note-preview" data-testid="note-preview">
                            <strong>Your note:</strong> {inst.dm_note}
                          </p>
                        )}
                      </>
                    ) : (
                      <p className="muted small">Hasn't brought a character yet.</p>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

function DmPlayerCharacter({ campaign, instanceId }: { campaign: Campaign; instanceId: number }) {
  return (
    <InstanceView
      url={`/api/campaigns/${campaign.id}/instances/${instanceId}`}
      back={
        <Link to={dmCampaignPath(campaign.id, "party")} className="back-link">
          ← Back to the party
        </Link>
      }
      dm
    />
  );
}

function PlayerPartyPage({ campaign }: { campaign: Campaign }) {
  return (
    <section aria-labelledby="page-title" data-testid="campaign-party">
      <PageHeading title="Party" summary={campaign.party ? `${campaign.party.name}, led by ${campaign.dm.name}.` : undefined} />
      <ul className="player-list" data-testid="player-list">
        {campaign.players.map((p) => (
          <li key={p.id} className="player-card" data-testid="player-card">
            <p className="player-name">{p.name}</p>
            {p.instance ? (
              <p className="small">
                {p.instance.name}, level {p.instance.level} {p.instance.class}
              </p>
            ) : (
              <p className="muted small">Hasn't brought a character yet.</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

// ================================================================ Session log
function SessionList({ sessions, onEdit }: { sessions: SessionEntry[]; onEdit?: (s: SessionEntry) => void }) {
  return (
    <section aria-labelledby={onEdit ? undefined : "page-title"}>
      {!onEdit && <PageHeading title="Session log" summary="What happened at the table, newest first." />}
      {sessions.length === 0 ? (
        <p className="muted" data-testid="no-sessions">
          No sessions written up yet.
        </p>
      ) : (
        <ol className="session-log" data-testid="session-log">
          {sessions.map((s) => (
            <li key={s.id} className="session-entry" data-testid="session-entry">
              <p className="session-date">{longDate(s.played_on)}</p>
              <h3 className="session-title">{s.title}</h3>
              {s.summary.split(/\n{2,}/).map((p, i) => (p ? <p key={i}>{p}</p> : null))}
              {onEdit && (
                <button type="button" className="btn ghost small" aria-label={`Edit ${s.title}`} onClick={() => onEdit(s)}>
                  Edit
                </button>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function DmSessions({ campaign, onChange }: PageProps) {
  const { flash } = useFlash();
  const blank = { played_on: today(), title: "", summary: "" };
  const [editing, setEditing] = useState<SessionEntry | null>(null);
  const [form, setForm] = useState(blank);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [deleting, setDeleting] = useState(false);

  function startEdit(s: SessionEntry) {
    setEditing(s);
    setForm({ played_on: s.played_on, title: s.title, summary: s.summary });
    setErrors({});
  }
  function reset() {
    setEditing(null);
    setForm(blank);
    setErrors({});
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const url = `/api/campaigns/${campaign.id}/sessions${editing ? `/${editing.id}` : ""}`;
    const res = editing
      ? await api.patch<{ campaign: Campaign }>(url, form)
      : await api.post<{ campaign: Campaign; message: string }>(url, form);
    if (!res.ok) {
      setErrors(res.data.errors ?? { title: res.data.error ?? "The session wasn't saved." });
      return;
    }
    onChange(res.data.campaign);
    flash("success", editing ? "Session updated." : res.data.message ?? "Session added.");
    reset();
  }

  return (
    <section aria-labelledby="page-title" data-testid="campaign-sessions">
      <PageHeading title="Session log" summary="Write up each session. Your players can read the log." />
      <form className="notes-form session-form" onSubmit={onSubmit} aria-label={editing ? "Edit the session" : "Add a session"}>
        <h3 className="leaf-heading">{editing ? `Editing “${editing.title}”` : "Add a session"}</h3>
        <div className="row wrap">
          <div className="field">
            <label htmlFor="session-date">Played on</label>
            <input
              id="session-date"
              type="date"
              value={form.played_on}
              aria-invalid={errors.played_on ? true : undefined}
              onChange={(e) => setForm({ ...form, played_on: e.target.value })}
            />
            {errors.played_on && <p className="field-error">{errors.played_on}</p>}
          </div>
          <div className="field grow">
            <label htmlFor="session-title">Title</label>
            <input
              id="session-title"
              value={form.title}
              maxLength={100}
              placeholder="The crypt door"
              aria-invalid={errors.title ? true : undefined}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            {errors.title && (
              <p className="field-error" data-testid="error-title">
                {errors.title}
              </p>
            )}
          </div>
        </div>
        <div className="field">
          <label htmlFor="session-summary">What happened</label>
          <textarea
            id="session-summary"
            rows={4}
            maxLength={5000}
            value={form.summary}
            onChange={(e) => setForm({ ...form, summary: e.target.value })}
          />
        </div>
        <div className="row end">
          {editing && (
            <>
              <button type="button" className="btn ghost small" onClick={() => setDeleting(true)}>
                Delete session
              </button>
              <button type="button" className="btn ghost small" onClick={reset}>
                Cancel
              </button>
            </>
          )}
          <button type="submit" className="btn primary small">
            {editing ? "Save session" : "Add to the log"}
          </button>
        </div>
      </form>
      <SessionList sessions={campaign.sessions} onEdit={startEdit} />
      {deleting && editing && (
        <ConfirmDialog
          title={`Delete “${editing.title}”?`}
          confirmLabel="Delete"
          onClose={() => setDeleting(false)}
          onConfirm={async () => {
            const res = await api.delete<{ campaign: Campaign; message: string }>(
              `/api/campaigns/${campaign.id}/sessions/${editing.id}`,
            );
            if (!res.ok) return res.data.error ?? "The session wasn't deleted.";
            onChange(res.data.campaign);
            flash("info", res.data.message);
            reset();
          }}
        >
          <p>The entry is torn out of the log for good.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}

// ================================================================ Encounters
function DmEncounters({ campaign, onChange }: PageProps) {
  const { flash } = useFlash();
  const [collections, setCollections] = useState<CollectionSummary[] | null>(null);
  const [choice, setChoice] = useState("");
  const encounters = campaign.encounters ?? [];
  const attached = new Set(encounters.map((e) => e.collection.id));

  useEffect(() => {
    void api
      .get<{ collections: CollectionSummary[] }>("/api/bestiary/collections")
      .then((res) => res.ok && setCollections(res.data.collections));
  }, []);

  async function attach(e: FormEvent) {
    e.preventDefault();
    if (!choice) return;
    const res = await api.put<{ campaign: Campaign; message: string }>(`/api/campaigns/${campaign.id}/encounters/${choice}`);
    if (!res.ok) {
      flash("error", res.data.error ?? "The collection wasn't added.");
      return;
    }
    onChange(res.data.campaign);
    setChoice("");
    flash("success", res.data.message);
  }

  async function detach(collectionId: number) {
    const res = await api.delete<{ campaign: Campaign; message: string }>(
      `/api/campaigns/${campaign.id}/encounters/${collectionId}`,
    );
    if (!res.ok) {
      flash("error", res.data.error ?? "The collection wasn't taken off.");
      return;
    }
    onChange(res.data.campaign);
    flash("info", res.data.message);
  }

  const available = (collections ?? []).filter((c) => !attached.has(c.id));
  const totalXp = encounters.reduce((sum, e) => sum + e.collection.total_xp, 0);

  return (
    <section aria-labelledby="page-title" data-testid="campaign-encounters">
      <PageHeading
        title="Encounters"
        summary="The monster collections from your bestiary that this campaign uses. Only you can see this page."
      />
      {collections && collections.length === 0 ? (
        <p className="muted" data-testid="no-collections">
          You haven't made any monster collections yet. <Link to={COLLECTIONS_PATH}>Start one in the bestiary</Link>.
        </p>
      ) : (
        <form className="row wrap inline-form" onSubmit={attach} aria-label="Add an encounter">
          <div className="field grow">
            <label htmlFor="encounter-collection">Monster collection</label>
            <select id="encounter-collection" value={choice} onChange={(e) => setChoice(e.target.value)}>
              <option value="">{available.length ? "Choose a collection…" : "Every collection is already here"}</option>
              {available.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({plural(c.monster_count, "monster")}, {xp(c.total_xp)})
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn primary small" disabled={!choice}>
            Add encounter
          </button>
        </form>
      )}

      {encounters.length === 0 ? (
        <p className="muted" data-testid="no-encounters">
          No encounters yet.
        </p>
      ) : (
        <>
          <p className="muted small" data-testid="encounter-totals">
            {plural(encounters.length, "encounter")} · {xp(totalXp)} in all
          </p>
          <ul className="collection-list" data-testid="encounter-list">
            {encounters.map(({ collection: c }) => (
              <li key={c.id} className="collection-card" data-testid="encounter">
                <Link to={collectionPath(c.id)} className="collection-name">
                  {c.name}
                </Link>
                <p className="muted small" data-testid="encounter-facts">
                  {plural(c.monster_count, "monster")} · {xp(c.total_xp)}
                  {c.roles.boss > 0 && ` · ${plural(c.roles.boss, "boss", "bosses")}`}
                </p>
                {c.notes && <p className="small">{c.notes}</p>}
                <button
                  type="button"
                  className="btn ghost small"
                  aria-label={`Take ${c.name} off the campaign`}
                  onClick={() => detach(c.id)}
                >
                  Take off
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

// ================================================================ DM notes
function DmNotes({ campaign, onChange }: PageProps) {
  const { flash } = useFlash();
  const [notes, setNotes] = useState(campaign.dm_notes ?? "");
  const dirty = notes !== (campaign.dm_notes ?? "");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await patchCampaign(campaign.id, { dm_notes: notes });
    if (!res.ok) {
      flash("error", res.data.errors?.dm_notes ?? res.data.error ?? "The notes weren't saved.");
      return;
    }
    onChange(res.data.campaign);
    flash("success", "Notes saved.");
  }

  return (
    <section aria-labelledby="page-title" data-testid="campaign-notes">
      <PageHeading title="DM notes" summary="Your private planning notes. Players never see this page." />
      <form onSubmit={onSubmit} className="notes-form" aria-label="DM notes">
        <label htmlFor="dm-notes" className="sr-only">
          DM notes
        </label>
        <textarea
          id="dm-notes"
          rows={14}
          maxLength={10000}
          value={notes}
          placeholder="Secrets, villains' plans, loose threads, what to prepare next…"
          onChange={(e) => setNotes(e.target.value)}
        />
        <div className="row end">
          <button type="submit" className="btn primary" disabled={!dirty}>
            Save notes
          </button>
        </div>
      </form>
    </section>
  );
}
