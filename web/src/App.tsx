import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { PdfPanelProvider } from "./context/PdfPanelContext";
import { CampaignListPage } from "./pages/CampaignListPage";
import { DocumentExplorerPage } from "./pages/DocumentExplorerPage";
import { DocumentPickerPage } from "./pages/DocumentPickerPage";
import { StatBlockDetailPage } from "./pages/StatBlockDetailPage";
import { StatBlocksPage } from "./pages/StatBlocksPage";

export default function App() {
  return (
    <BrowserRouter>
      <PdfPanelProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<CampaignListPage />} />
            <Route path="campaigns/:campaignId" element={<DocumentPickerPage />} />
            <Route path="documents/:documentId" element={<DocumentExplorerPage />} />
            <Route
              path="documents/:documentId/chunks/:chunkId"
              element={<DocumentExplorerPage />}
            />
            <Route path="documents/:documentId/stat-blocks" element={<StatBlocksPage />} />
            <Route
              path="documents/:documentId/stat-blocks/:name"
              element={<StatBlockDetailPage />}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </PdfPanelProvider>
    </BrowserRouter>
  );
}
