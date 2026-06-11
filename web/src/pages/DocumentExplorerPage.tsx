import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { apiFetch } from "../api/client";
import type { Chunk, ChunkListItem, Section } from "../api/types";
import { ChunkList } from "../components/chunks/ChunkList";
import { ChunkReader } from "../components/chunks/ChunkReader";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { PdfSourcePanel } from "../components/pdf/PdfSourcePanel";
import { SectionTree } from "../components/sections/SectionTree";
import { usePdfPanel } from "../context/PdfPanelContext";

type MobileTab = "sections" | "content" | "pdf";

export function DocumentExplorerPage() {
  const { documentId = "", chunkId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const pdfPanel = usePdfPanel();

  const sectionId = searchParams.get("section");
  const [sections, setSections] = useState<Section[]>([]);
  const [chunks, setChunks] = useState<ChunkListItem[]>([]);
  const [chunk, setChunk] = useState<Chunk | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileTab, setMobileTab] = useState<MobileTab>("content");

  useEffect(() => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
    apiFetch<Section[]>(`/documents/${documentId}/sections`)
      .then((data) => {
        setSections(data);
        const selected =
          sectionId && data.some((section) => section.id === sectionId)
            ? sectionId
            : (data[0]?.id ?? null);
        if (selected && selected !== sectionId) {
          setSearchParams({ section: selected }, { replace: true });
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erreur"))
      .finally(() => setLoading(false));
  }, [documentId]);

  useEffect(() => {
    if (!documentId || !sectionId) {
      setChunks([]);
      return;
    }
    apiFetch<ChunkListItem[]>(
      `/documents/${documentId}/chunks?section_id=${encodeURIComponent(sectionId)}&limit=50`,
    )
      .then(setChunks)
      .catch((err) => setError(err instanceof Error ? err.message : "Erreur"));
  }, [documentId, sectionId]);

  useEffect(() => {
    if (!chunkId) {
      setChunk(null);
      return;
    }
    apiFetch<Chunk>(`/chunks/${chunkId}`)
      .then(setChunk)
      .catch((err) => setError(err instanceof Error ? err.message : "Chunk introuvable"));
  }, [chunkId]);

  const selectSection = (id: string) => {
    setSearchParams({ section: id });
    navigate(`/documents/${documentId}`);
    setMobileTab("content");
  };

  if (loading) {
    return <LoadingState />;
  }

  if (error && sections.length === 0) {
    return <ErrorState message={error} />;
  }

  const pdfVisible = pdfPanel.open && pdfPanel.page !== null;

  return (
    <>
      <div className="mobile-tabs">
        <button
          type="button"
          className={mobileTab === "sections" ? "active" : ""}
          onClick={() => setMobileTab("sections")}
        >
          Sections
        </button>
        <button
          type="button"
          className={mobileTab === "content" ? "active" : ""}
          onClick={() => setMobileTab("content")}
        >
          Contenu
        </button>
        <button
          type="button"
          className={mobileTab === "pdf" ? "active" : ""}
          onClick={() => setMobileTab("pdf")}
          disabled={!pdfVisible}
        >
          PDF
        </button>
      </div>

      <div className={`explorer-layout${pdfVisible ? " with-pdf" : ""}`}>
        <aside
          className={`explorer-column side ${mobileTab === "sections" ? "active" : ""}`}
        >
          <h2 className="panel-title">Sections</h2>
          <SectionTree
            sections={sections}
            selectedId={sectionId}
            onSelect={selectSection}
          />
        </aside>

        <section
          className={`explorer-column ${mobileTab === "content" ? "active" : ""}`}
        >
          <h2 className="panel-title">{chunk ? "Chunk" : "Chunks"}</h2>
          {chunk ? (
            <ChunkReader chunk={chunk} />
          ) : (
            <ChunkList
              documentId={documentId}
              chunks={chunks}
            />
          )}
        </section>

        <aside
          className={`explorer-column pdf-desktop ${
            mobileTab === "pdf" ? "pdf-mobile active" : ""
          }`}
          style={{ display: pdfVisible ? undefined : "none" }}
        >
          {pdfVisible && (
            <PdfSourcePanel
              documentId={documentId}
              page={pdfPanel.page!}
              highlight={pdfPanel.highlight}
            />
          )}
        </aside>
      </div>

      {pdfPanel.mobileOpen && pdfVisible && (
        <>
          <div
            className="pdf-modal-backdrop"
            onClick={pdfPanel.closePanel}
            aria-hidden
          />
          <div className="pdf-modal pdf-mobile active">
            <PdfSourcePanel
              documentId={documentId}
              page={pdfPanel.page!}
              highlight={pdfPanel.highlight}
              onClose={pdfPanel.closePanel}
            />
          </div>
        </>
      )}
    </>
  );
}
