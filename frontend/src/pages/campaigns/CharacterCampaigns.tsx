import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { PLAYER_CAMPAIGNS_PATH, instanceLine, playerCampaignPath, type InstanceSummary, type Person } from "../../lib/campaigns";
import { PageHeading } from "../characters/CharacterTome";
import { HpBar } from "./InstancePages";

interface Row {
  campaign: { id: number; name: string; status: string; status_label: string; dm: Person; in_party: boolean };
  instance: InstanceSummary;
}

/** Character Manager › a character › Campaigns: the copies of this character playing in campaigns. */
export function CharacterCampaignsPage({ characterId, name }: { characterId: number; name: string }) {
  const [rows, setRows] = useState<Row[] | null>(null);

  useEffect(() => {
    void api.get<{ campaigns: Row[] }>(`/api/campaigns/characters/${characterId}`).then((res) => res.ok && setRows(res.data.campaigns));
  }, [characterId]);

  return (
    <section aria-labelledby="page-title" data-testid="character-campaigns">
      <PageHeading
        title="Campaigns"
        summary={`Each campaign keeps its own copy of ${name}, with its own level, hit points and items. The character on these pages never changes.`}
      />
      {rows?.length === 0 && (
        <div className="empty-page" data-testid="no-character-campaigns">
          <p>{name} isn't in any campaigns yet. Bring them from a campaign's “Your character” page.</p>
          <Link to={PLAYER_CAMPAIGNS_PATH} className="btn ghost">
            Your campaigns
          </Link>
        </div>
      )}
      {rows && rows.length > 0 && (
        <ul className="campaign-list" data-testid="character-campaign-list">
          {rows.map(({ campaign, instance }) => (
            <li key={instance.id} className="campaign-card" data-testid="character-campaign">
              <div className="row between wrap">
                {campaign.in_party ? (
                  <Link to={playerCampaignPath(campaign.id, "character")} className="campaign-name">
                    {campaign.name}
                  </Link>
                ) : (
                  <span className="campaign-name">{campaign.name}</span>
                )}
                <span className={`pill status-${campaign.status}`}>{campaign.status_label}</span>
              </div>
              <p className="small">
                {instanceLine(instance)} · Dungeon Master: {campaign.dm.name}
              </p>
              <HpBar instance={instance} />
              {!campaign.in_party && <p className="muted small">You've left this campaign's party; the copy is kept.</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
