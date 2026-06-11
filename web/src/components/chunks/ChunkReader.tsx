import { Link } from "react-router-dom";

import type { Chunk } from "../../api/types";
import { usePdfPanel } from "../../context/PdfPanelContext";

function firstSourcePage(chunk: Chunk): number {
  if (chunk.source_spans.length > 0) {
    return chunk.source_spans[0].page;
  }
  return chunk.page_start;
}

function highlightFromChunk(chunk: Chunk) {
  const pageBlockIds = chunk.source_spans.flatMap((span) => span.page_block_ids);
  const bboxFallbacks = chunk.source_spans
    .map((span) => span.bbox)
    .filter((bbox): bbox is NonNullable<typeof bbox> => bbox !== null);
  return { pageBlockIds, bboxFallbacks };
}

export function ChunkReader({ chunk }: { chunk: Chunk }) {
  const { showSource } = usePdfPanel();
  const statName =
    chunk.chunk_type_hint === "stat_block"
      ? ((chunk.metadata.stat_block as { name?: string } | undefined)?.name ?? null)
      : null;

  return (
    <article className="chunk-reader">
      <div className="chunk-meta">
        <span className="badge">{chunk.chunk_type ?? chunk.chunk_type_hint ?? "chunk"}</span>
        <span>p.{chunk.page_start}
          {chunk.page_end !== chunk.page_start ? `–${chunk.page_end}` : ""}
        </span>
        <span>{chunk.token_count} tokens</span>
        {chunk.needs_rechunk && <span className="badge">needs_rechunk</span>}
      </div>

      <div className="chunk-actions">
        <button
          type="button"
          className="btn primary"
          onClick={() => showSource(firstSourcePage(chunk), highlightFromChunk(chunk))}
        >
          Voir la source
        </button>
        {statName && (
          <Link
            className="btn"
            to={`/documents/${chunk.document_id}/stat-blocks/${encodeURIComponent(statName)}`}
          >
            Fiche {statName}
          </Link>
        )}
      </div>

      <pre>{chunk.text}</pre>

      <details style={{ marginTop: "1rem" }}>
        <summary className="muted">Métadonnées</summary>
        <pre style={{ fontSize: "0.85rem" }}>
          {JSON.stringify(
            {
              source_spans: chunk.source_spans,
              metadata: chunk.metadata,
            },
            null,
            2,
          )}
        </pre>
      </details>
    </article>
  );
}
