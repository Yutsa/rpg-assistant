import { Routes } from '@angular/router';

import { ChunkDetailPage } from './pages/chunk-detail/chunk-detail.page';
import { DocumentExplorerPage } from './pages/document-explorer/document-explorer.page';
import { PageLayoutViewerPage } from './pages/page-layout-viewer/page-layout-viewer.page';
import { StatBlockDetailPage } from './pages/stat-block-detail/stat-block-detail.page';

export const DOCUMENT_ROUTES: Routes = [
  {
    path: ':documentId/pages/:pageNumber',
    component: PageLayoutViewerPage,
  },
  {
    path: ':documentId',
    component: DocumentExplorerPage,
    children: [
      { path: 'chunks/:chunkId', component: ChunkDetailPage },
      { path: 'stat-blocks/:statBlockId', component: StatBlockDetailPage },
    ],
  },
];
