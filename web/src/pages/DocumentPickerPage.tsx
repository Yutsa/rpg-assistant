import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { CampaignSummary, Document } from "../api/types";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";

export function DocumentPickerPage() {
  const { campaignId = "" } = useParams();
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [summary, setSummary] = useState<CampaignSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    if (!campaignId) return;
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch<Document[]>(`/campaigns/${campaignId}/documents`),
      apiFetch<CampaignSummary>(`/campaigns/${campaignId}/summary`),
    ])
      .then(([docs, sum]) => {
        setDocuments(docs);
        setSummary(sum);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erreur réseau"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [campaignId]);

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

  if (!documents?.length) {
    return (
      <main className="page">
        <div className="state-box">
          <h2>Aucun document pour {campaignId}</h2>
          <p className="muted">Importez un PDF avec la CLI pour cette campagne.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <h2>Documents — {campaignId}</h2>
      {summary && (
        <p className="muted">
          {summary.section_count} sections · {summary.chunk_count} chunks · {summary.entities} entités
        </p>
      )}
      <div className="card-grid">
        {documents.map((doc) => (
          <Link key={doc.id} className="card" to={`/documents/${doc.id}`}>
            <h3>{doc.filename}</h3>
            <p className="muted">
              {doc.page_count} pages · {doc.section_count} sections · {doc.chunk_count} chunks
            </p>
            {doc.latest_ingestion_status && (
              <p className="muted">Import raw : {doc.latest_ingestion_status}</p>
            )}
          </Link>
        ))}
      </div>
    </main>
  );
}
