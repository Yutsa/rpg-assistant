import { Link } from "react-router-dom";

import type { ChunkListItem } from "../../api/types";

export function ChunkList({
  documentId,
  chunks,
  selectedChunkId,
}: {
  documentId: string;
  chunks: ChunkListItem[];
  selectedChunkId?: string | null;
}) {
  if (chunks.length === 0) {
    return <p className="muted" style={{ padding: "1rem" }}>Aucun chunk pour cette section.</p>;
  }

  return (
    <ul className="chunk-list">
      {chunks.map((chunk) => (
        <li key={chunk.id} className="chunk-item">
          <Link
            to={`/documents/${documentId}/chunks/${chunk.id}`}
            className={selectedChunkId === chunk.id ? "active" : ""}
          >
            <div className="chunk-meta">
              <span>p.{chunk.page_start}
                {chunk.page_end !== chunk.page_start ? `–${chunk.page_end}` : ""}
              </span>
              {chunk.chunk_type && <span className="badge">{chunk.chunk_type}</span>}
              {chunk.chunk_type_hint === "stat_block" && (
                <span className="badge stat">stat_block</span>
              )}
              <span>{chunk.token_count} tokens</span>
            </div>
            <div>{chunk.text_preview || "…"}</div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
