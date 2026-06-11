import { useCallback, useEffect, useState } from "react";

const storageKey = (documentId: string) => `rpg-assistant:pdf-path:${documentId}`;

export function usePdfPath(documentId: string) {
  const [pdfPath, setPdfPathState] = useState<string | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }
    return localStorage.getItem(storageKey(documentId));
  });
  const [needsOverride, setNeedsOverride] = useState(false);
  const [draftPath, setDraftPath] = useState("");

  useEffect(() => {
    const stored = localStorage.getItem(storageKey(documentId));
    setPdfPathState(stored);
    setDraftPath(stored ?? "");
    setNeedsOverride(false);
  }, [documentId]);

  const setPdfPath = useCallback(
    (path: string | null) => {
      const trimmed = path?.trim() || null;
      if (trimmed) {
        localStorage.setItem(storageKey(documentId), trimmed);
      } else {
        localStorage.removeItem(storageKey(documentId));
      }
      setPdfPathState(trimmed);
      setNeedsOverride(false);
    },
    [documentId],
  );

  const saveDraft = useCallback(() => {
    setPdfPath(draftPath || null);
  }, [draftPath, setPdfPath]);

  const clearPath = useCallback(() => {
    setPdfPath(null);
    setDraftPath("");
  }, [setPdfPath]);

  return {
    pdfPath,
    needsOverride,
    setNeedsOverride,
    draftPath,
    setDraftPath,
    setPdfPath,
    saveDraft,
    clearPath,
  };
}
