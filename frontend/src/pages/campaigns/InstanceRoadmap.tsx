import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { instanceLine, longDate, type Campaign, type InstanceDetail } from "../../lib/campaigns";
import { useFlash } from "../../lib/flash";
import { levelRange, roadmapPath, roadmapsPath } from "../../lib/roadmaps";
import { ConfirmDialog } from "../bestiary/ConfirmDialog";

type Detail = InstanceDetail & { message?: string };

/**
 * A campaign › Your character: follow one of the character's level roadmaps.
 *
 * Earlier picks are locked in a campaign, so a roadmap can only be followed when its plan for the
 * character's level matches the choices already made. From then on, Level Up fills in the roadmap's
 * picks for each new level. Following asks first, and offers to keep a backup copy.
 */
export function RoadmapPanel({
  campaign,
  detail,
  onChange,
}: {
  campaign: Campaign;
  detail: InstanceDetail;
  onChange: (d: InstanceDetail) => void;
}) {
  const { flash } = useFlash();
  const i = detail.instance;
  const url = `/api/campaigns/${campaign.id}/instance/roadmap`;
  const roadmaps = i.roadmaps ?? [];
  const following = i.following ?? null;
  const [choice, setChoice] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [keepBackup, setKeepBackup] = useState(true);
  const [busy, setBusy] = useState(false);
  const chosen = roadmaps.find((r) => String(r.id) === choice);

  async function send(method: "post" | "delete", path: string) {
    setBusy(true);
    const res = method === "post" ? await api.post<Detail>(path) : await api.delete<Detail>(path);
    setBusy(false);
    if (!res.ok) {
      flash("error", res.data.error ?? "That didn't work.");
      return;
    }
    onChange(res.data);
    if (res.data.message) flash("success", res.data.message);
  }

  return (
    <section className="instance-roadmap" aria-labelledby="roadmap-heading" data-testid="instance-roadmap">
      <h3 id="roadmap-heading" className="leaf-heading">
        Level roadmap
      </h3>
      {following ? (
        <>
          <p data-testid="following">
            Following <strong>{following.name}</strong> ({levelRange(following).toLowerCase()}).
          </p>
          <div className="row wrap">
            {following.next_level ? (
              i.progress.can_level_up ? (
                <Link to={`/play/campaigns/c/${campaign.id}/character/level-up`} className="btn primary small">
                  Level up to {following.next_level} with the roadmap
                </Link>
              ) : (
                <p className="hint">The roadmap plans level {following.next_level} for when it's ready.</p>
              )
            ) : (
              <p className="hint" data-testid="roadmap-ends">
                The roadmap ends at level {following.end_level}.{" "}
                {i.base_character && (
                  <Link to={roadmapPath(i.base_character.id, following.roadmap_id)}>Plan more levels</Link>
                )}{" "}
                or level up by hand.
              </p>
            )}
            <button type="button" className="btn ghost small" disabled={busy} onClick={() => void send("delete", url)}>
              Stop following
            </button>
          </div>
        </>
      ) : !i.base_character ? (
        <p className="hint">The original character was deleted, so there are no roadmaps to follow.</p>
      ) : roadmaps.length === 0 ? (
        <p className="hint" data-testid="no-instance-roadmaps">
          {i.base_character.name} has no roadmaps yet.{" "}
          <Link to={roadmapsPath(i.base_character.id)}>Plan one in the Character Manager</Link> to level up along it here.
        </p>
      ) : (
        <form
          className="row wrap"
          aria-label="Follow a roadmap"
          onSubmit={(e) => {
            e.preventDefault();
            setKeepBackup(true);
            setConfirming(true);
          }}
        >
          <label className="compact">
            <span>Roadmap</span>
            <select value={choice} onChange={(e) => setChoice(e.target.value)}>
              <option value="">Choose…</option>
              {roadmaps.map((r) => (
                <option key={r.id} value={r.id} disabled={!r.covers_level}>
                  {r.name} ({levelRange(r).toLowerCase()})
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn ghost small" disabled={!chosen}>
            Follow
          </button>
          {roadmaps.some((r) => !r.covers_level) && (
            <p className="hint">Roadmaps that don't plan level {i.level} yet can't be followed until they do.</p>
          )}
        </form>
      )}

      {confirming && chosen && (
        <ConfirmDialog
          title={`Follow “${chosen.name}”?`}
          confirmLabel="Follow the roadmap"
          cancelLabel="Not now"
          tone="primary"
          onClose={() => setConfirming(false)}
          onConfirm={async () => {
            const res = await api.put<Detail>(url, {
              roadmap_id: chosen.id,
              backup: keepBackup,
              overwrite_backup: keepBackup && Boolean(i.backup),
            });
            if (!res.ok) {
              const problems = (res.data as unknown as { errors?: { message: string }[] | Record<string, string> }).errors;
              const first = Array.isArray(problems) ? problems[0]?.message : problems ? Object.values(problems)[0] : null;
              return [res.data.error, first].filter(Boolean).join(" ") || "The roadmap wasn't followed.";
            }
            onChange(res.data);
            if (res.data.message) flash("success", res.data.message);
          }}
        >
          <p>
            From now on, Level Up fills in the roadmap's picks for each new level of {i.name} in {campaign.name}. Earlier
            picks are locked in a campaign, so the roadmap has to match the choices {i.name} already made up to level{" "}
            {i.level}. Items and hit points stay as they are.
          </p>
          <label className="check">
            <input type="checkbox" checked={keepBackup} onChange={(e) => setKeepBackup(e.target.checked)} />
            Save {i.name} as they are now as the backup first
          </label>
          {keepBackup && i.backup && (
            <p className="hint" data-testid="replaces-backup">
              This replaces the backup saved on {longDate(i.backup.saved_at)} ({instanceLine(i.backup)}).
            </p>
          )}
        </ConfirmDialog>
      )}
    </section>
  );
}

type BackupAction = "restore" | "overwrite" | "delete";

/** A campaign › Your character: the one backup copy a player can keep in each campaign. */
export function BackupPanel({
  campaign,
  detail,
  onChange,
}: {
  campaign: Campaign;
  detail: InstanceDetail;
  onChange: (d: InstanceDetail) => void;
}) {
  const { flash } = useFlash();
  const i = detail.instance;
  const b = i.backup ?? null;
  const url = `/api/campaigns/${campaign.id}/instance/backup`;
  const [action, setAction] = useState<BackupAction | null>(null);

  async function run(kind: "save" | BackupAction): Promise<string | void> {
    const res =
      kind === "restore"
        ? await api.post<Detail>(`${url}/restore`)
        : kind === "delete"
          ? await api.delete<Detail>(url)
          : await api.put<Detail>(url, { overwrite: kind === "overwrite" });
    if (!res.ok) return res.data.error ?? "The backup wasn't changed.";
    onChange(res.data);
    if (res.data.message) flash("success", res.data.message);
  }

  const dialogs: Record<BackupAction, { title: string; label: string; body: string; tone: "primary" | "danger" }> = {
    restore: {
      title: "Restore the backup?",
      label: "Swap them",
      tone: "primary",
      body: `${i.name} goes back to the backup (${b ? instanceLine(b) : ""}). The character as they are now becomes the backup, so nothing is lost and you can swap back.`,
    },
    overwrite: {
      title: "Replace the backup?",
      label: "Replace the backup",
      tone: "danger",
      body: `Each campaign keeps one backup. The one saved on ${b ? longDate(b.saved_at) : ""} (${b ? instanceLine(b) : ""}) is replaced by ${i.name} as they are now.`,
    },
    delete: {
      title: "Delete the backup?",
      label: "Delete the backup",
      tone: "danger",
      body: "The backup copy is gone for good. Your character as they are now isn't affected.",
    },
  };

  return (
    <section className="instance-backup" aria-labelledby="backup-heading" data-testid="instance-backup">
      <h3 id="backup-heading" className="leaf-heading">
        Backup copy
      </h3>
      {b ? (
        <>
          <p data-testid="backup-summary">
            <strong>{instanceLine(b)}</strong> · {b.current_hp}/{b.max_hp} HP · saved {longDate(b.saved_at)}
            {b.reason && <span className="muted"> · {b.reason}</span>}
          </p>
          <div className="row wrap">
            <button type="button" className="btn ghost small" onClick={() => setAction("restore")}>
              Restore backup
            </button>
            <button type="button" className="btn ghost small" onClick={() => setAction("overwrite")}>
              Back up again
            </button>
            <button type="button" className="btn ghost small" onClick={() => setAction("delete")}>
              Delete backup
            </button>
          </div>
        </>
      ) : (
        <div className="row wrap">
          <p className="hint">
            Keep one copy of {i.name} in this campaign to come back to, say before a big level-up or switching roadmaps.
          </p>
          <button type="button" className="btn ghost small" onClick={() => void run("save")}>
            Save a backup
          </button>
        </div>
      )}
      {action && (
        <ConfirmDialog
          title={dialogs[action].title}
          confirmLabel={dialogs[action].label}
          cancelLabel="Keep things as they are"
          tone={dialogs[action].tone}
          onClose={() => setAction(null)}
          onConfirm={() => run(action)}
        >
          <p>{dialogs[action].body}</p>
        </ConfirmDialog>
      )}
    </section>
  );
}
