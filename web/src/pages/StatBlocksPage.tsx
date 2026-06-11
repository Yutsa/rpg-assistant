import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { StatBlockIndexEntry } from "../api/types";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { StatBlockCard } from "../components/statblocks/StatBlockCard";

export function StatBlocksPage() {
  const { documentId = "" } = useParams();
  const [entries, setEntries] = useState<StatBlockIndexEntry[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!documentId) return;
    setLoading(true);
    apiFetch<StatBlockIndexEntry[]>(`/documents/${documentId}/stat-blocks`)
      .then(setEntries)
      .catch((err) => setError(err instanceof Error ? err.message : "Erreur"))
      .finally(() => setLoading(false));
  }, [documentId]);

  const filtered = useMemo(() => {
    const query = filter.trim().toLowerCase();
    const sorted = [...entries].sort((a, b) => a.name.localeCompare(b.name, "fr"));
    if (!query) return sorted;
    return sorted.filter((entry) => entry.name.toLowerCase().includes(query));
  }, [entries, filter]);

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
        <ErrorState message={error} />
      </main>
    );
  }

  return (
    <main className="page">
      <h2>Fiches COF2</h2>
      <input
        type="search"
        placeholder="Filtrer par nom…"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        style={{
          width: "100%",
          maxWidth: "420px",
          padding: "0.5rem",
          marginBottom: "1rem",
          border: "1px solid var(--border)",
          borderRadius: "8px",
        }}
      />
      {filtered.length === 0 ? (
        <p className="muted">Aucune fiche stat pour ce document.</p>
      ) : (
        <div className="card-grid">
          {filtered.map((entry) => (
            <StatBlockCard key={entry.chunk_id} documentId={documentId} entry={entry} />
          ))}
        </div>
      )}
    </main>
  );
}
