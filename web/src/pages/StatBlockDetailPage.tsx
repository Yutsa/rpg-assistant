import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiClientError, apiFetch } from "../api/client";
import type { ApiErrorBody, StatBlockDetail } from "../api/types";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { PdfSourcePanel } from "../components/pdf/PdfSourcePanel";
import { StatBlockDetailView } from "../components/statblocks/StatBlockDetailView";
import { usePdfPanel } from "../context/PdfPanelContext";

export function StatBlockDetailPage() {
  const { documentId = "", name = "" } = useParams();
  const decodedName = decodeURIComponent(name);
  const [detail, setDetail] = useState<StatBlockDetail | null>(null);
  const [candidates, setCandidates] = useState<ApiErrorBody["candidates"]>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const pdfPanel = usePdfPanel();

  useEffect(() => {
    if (!documentId || !decodedName) return;
    setLoading(true);
    setError(null);
    setCandidates(undefined);
    apiFetch<StatBlockDetail>(
      `/documents/${documentId}/stat-blocks/${encodeURIComponent(decodedName)}`,
    )
      .then(setDetail)
      .catch((err) => {
        if (err instanceof ApiClientError && err.status === 422) {
          setCandidates(err.body.candidates);
          setError("Plusieurs fiches correspondent à ce nom.");
        } else {
          setError(err instanceof Error ? err.message : "Fiche introuvable");
        }
      })
      .finally(() => setLoading(false));
  }, [documentId, decodedName]);

  if (loading) {
    return (
      <main className="page">
        <LoadingState />
      </main>
    );
  }

  if (candidates?.length) {
    return (
      <main className="page">
        <div className="state-box">
          <p>{error}</p>
          <ul>
            {candidates.map((candidate) => (
              <li key={candidate.chunk_id}>
                <Link
                  to={`/documents/${documentId}/stat-blocks/${encodeURIComponent(candidate.name)}`}
                >
                  {candidate.name} (NC {candidate.nc ?? "—"}, p.{candidate.pages.start})
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </main>
    );
  }

  if (error || !detail) {
    return (
      <main className="page">
        <ErrorState message={error ?? "Fiche introuvable"} />
      </main>
    );
  }

  const pdfVisible = pdfPanel.open && pdfPanel.page !== null;

  return (
    <div className="explorer-layout" style={{ minHeight: "60vh" }}>
      <section className="explorer-column" style={{ borderRight: "1px solid var(--border)" }}>
        <StatBlockDetailView detail={detail} />
      </section>
      {pdfVisible && (
        <aside className="explorer-column">
          <PdfSourcePanel
            documentId={documentId}
            page={pdfPanel.page!}
            highlight={pdfPanel.highlight}
          />
        </aside>
      )}
    </div>
  );
}
