import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { PdfHighlight } from "../api/types";

interface PdfPanelState {
  open: boolean;
  page: number | null;
  highlight: PdfHighlight | null;
}

interface PdfPanelContextValue extends PdfPanelState {
  showSource: (page: number, highlight: PdfHighlight) => void;
  closePanel: () => void;
  setMobileOpen: (open: boolean) => void;
  mobileOpen: boolean;
}

const PdfPanelContext = createContext<PdfPanelContextValue | null>(null);

export function PdfPanelProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PdfPanelState>({
    open: false,
    page: null,
    highlight: null,
  });
  const [mobileOpen, setMobileOpen] = useState(false);

  const showSource = useCallback((page: number, highlight: PdfHighlight) => {
    setState({ open: true, page, highlight });
    const isNarrow =
      typeof window !== "undefined" &&
      window.matchMedia("(max-width: 900px)").matches;
    setMobileOpen(isNarrow);
  }, []);

  const closePanel = useCallback(() => {
    setState({ open: false, page: null, highlight: null });
    setMobileOpen(false);
  }, []);

  const value = useMemo(
    () => ({
      ...state,
      showSource,
      closePanel,
      mobileOpen,
      setMobileOpen,
    }),
    [state, showSource, closePanel, mobileOpen],
  );

  return (
    <PdfPanelContext.Provider value={value}>{children}</PdfPanelContext.Provider>
  );
}

export function usePdfPanel() {
  const ctx = useContext(PdfPanelContext);
  if (!ctx) {
    throw new Error("usePdfPanel must be used within PdfPanelProvider");
  }
  return ctx;
}
