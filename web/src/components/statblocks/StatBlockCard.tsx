import { Link } from "react-router-dom";

import type { StatBlockIndexEntry } from "../../api/types";

export function StatBlockCard({
  documentId,
  entry,
}: {
  documentId: string;
  entry: StatBlockIndexEntry;
}) {
  return (
    <Link
      className="card"
      to={`/documents/${documentId}/stat-blocks/${encodeURIComponent(entry.name)}`}
    >
      <h3>{entry.name}</h3>
      <p className="muted">
        NC {entry.nc ?? "—"} · p.{entry.pages.start}
        {entry.pages.end !== entry.pages.start ? `–${entry.pages.end}` : ""}
      </p>
    </Link>
  );
}
