import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { Campaign } from "../api/types";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";

export function CampaignListPage() {
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    setError(null);
    apiFetch<Campaign[]>("/campaigns")
      .then(setCampaigns)
      .catch((err) => setError(err instanceof Error ? err.message : "Erreur réseau"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return (
      <main className="page">
        <LoadingState />
      </main>
    );
  }

  if (error) {
    return (
      <main className="page">
        <ErrorState message={error} onRetry={load} />
      </main>
    );
  }

  if (!campaigns?.length) {
    return (
      <main className="page">
        <div className="state-box">
          <h2>Aucune campagne importée</h2>
          <p className="muted">
            Importez un PDF via la CLI&nbsp;:
          </p>
          <pre style={{ textAlign: "left", overflow: "auto" }}>
            {`uv run rpg-ingest raw extract <fichier.pdf> \\
  --campaign-id momie --game-system cof2`}
          </pre>
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <h2>Campagnes</h2>
      <div className="card-grid">
        {campaigns.map((campaign) => (
          <Link key={campaign.id} className="card" to={`/campaigns/${campaign.id}`}>
            <h3>{campaign.title || campaign.id}</h3>
            <p className="muted">
              {campaign.document_count} document(s)
              {campaign.game_system ? ` · ${campaign.game_system}` : ""}
            </p>
          </Link>
        ))}
      </div>
    </main>
  );
}
