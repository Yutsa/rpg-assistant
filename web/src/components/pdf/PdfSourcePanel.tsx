import { useCallback, useEffect, useState } from "react";

import { ApiClientError, apiFetch, pageRenderUrl } from "../../api/client";
import type { PageBlock, PageMeta, PdfHighlight } from "../../api/types";
import { usePdfPath } from "../../hooks/usePdfPath";
import { BboxOverlay } from "./BboxOverlay";

export function PdfSourcePanel({
  documentId,
  page,
  highlight,
  onClose,
}: {
  documentId: string;
  page: number;
  highlight: PdfHighlight | null;
  onClose?: () => void;
}) {
  const { pdfPath, needsOverride, setNeedsOverride, draftPath, setDraftPath, saveDraft, clearPath } =
    usePdfPath(documentId);
  const [meta, setMeta] = useState<PageMeta | null>(null);
  const [blocks, setBlocks] = useState<PageBlock[]>([]);
  const [imageWidth, setImageWidth] = useState(0);
  const [imageHeight, setImageHeight] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const renderSrc = pageRenderUrl(documentId, page, { dpi: 150, pdfPath });

  const loadMeta = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pageMeta, pageBlocks] = await Promise.all([
        apiFetch<PageMeta>(`/documents/${documentId}/pages/${page}`),
        apiFetch<PageBlock[]>(`/documents/${documentId}/pages/${page}/blocks`),
      ]);
      setMeta(pageMeta);
      setBlocks(pageBlocks);
    } catch (err) {
      if (err instanceof ApiClientError && err.body.code === "pdf_not_found") {
        setNeedsOverride(true);
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Erreur de chargement");
      }
    } finally {
      setLoading(false);
    }
  }, [documentId, page, setNeedsOverride]);

  useEffect(() => {
    void loadMeta();
  }, [loadMeta]);

  const handleImageLoad = (img: HTMLImageElement) => {
    setImageWidth(img.clientWidth);
    setImageHeight(img.clientHeight);
  };

  const handleImageError = () => {
    setNeedsOverride(true);
    setError(
      "Impossible de charger l'image PDF. Indiquez le chemin absolu du fichier source.",
    );
  };

  return (
    <div className="pdf-panel">
      <div className="pdf-toolbar">
        <strong>Source PDF — page {page}</strong>
        {onClose && (
          <button type="button" className="btn" onClick={onClose}>
            Fermer
          </button>
        )}
      </div>

      {(needsOverride || error) && (
        <div className="pdf-banner">
          <p>
            {error ??
              "PDF introuvable sur ce poste. Collez le chemin absolu du fichier (réimport CLI si déplacé)."}
          </p>
          <input
            type="text"
            placeholder="/chemin/vers/aventure.pdf"
            value={draftPath}
            onChange={(event) => setDraftPath(event.target.value)}
          />
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
            <button type="button" className="btn primary" onClick={saveDraft}>
              Enregistrer le chemin
            </button>
            {pdfPath && (
              <button type="button" className="btn" onClick={clearPath}>
                Effacer
              </button>
            )}
          </div>
        </div>
      )}

      <div className="pdf-viewport">
        {loading && <p className="muted">Chargement de la page…</p>}
        {!loading && meta && (
          <div style={{ position: "relative", display: "inline-block" }}>
            <img
              key={renderSrc}
              src={renderSrc}
              alt={`Page ${page}`}
              onLoad={(event) => handleImageLoad(event.currentTarget)}
              onError={handleImageError}
            />
            {imageWidth > 0 && (
              <BboxOverlay
                blocks={blocks}
                highlight={highlight}
                pageWidthPts={meta.width}
                imageWidthPx={imageWidth}
                imageHeightPx={imageHeight}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
