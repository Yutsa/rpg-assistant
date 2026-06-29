import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';
import { PdfViewerService } from '../../../../core/services/pdf-viewer.service';
import { ChunkListItem, SectionNode, StatBlockIndex } from '../../../../core/models/campaign.models';
import { buildSectionTree } from '../../../../core/utils/section-tree';
import { ChunkListComponent } from '../../../../shared/components/chunk-list/chunk-list.component';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { SectionTreeComponent } from '../../../../shared/components/section-tree/section-tree.component';
import { PageLayoutViewerComponent } from '../../../../shared/components/page-layout-viewer/page-layout-viewer.component';
import { StatBlockListComponent } from '../../../../shared/components/stat-block-list/stat-block-list.component';

const CHUNK_PAGE_SIZE = 20;

@Component({
  selector: 'app-document-explorer-page',
  imports: [
    RouterOutlet,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatTabsModule,
    MatTooltipModule,
    MatProgressSpinnerModule,
    SectionTreeComponent,
    ChunkListComponent,
    StatBlockListComponent,
    PageLayoutViewerComponent,
    EmptyStateComponent,
  ],
  templateUrl: './document-explorer.page.html',
  styleUrl: './document-explorer.page.scss',
})
export class DocumentExplorerPage {
  private readonly api = inject(CampaignApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly pdfViewer = inject(PdfViewerService);

  readonly documentId = this.route.snapshot.paramMap.get('documentId') ?? '';
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly sectionTree = signal<SectionNode[]>([]);
  readonly chunks = signal<ChunkListItem[]>([]);
  readonly statBlocks = signal<StatBlockIndex[]>([]);
  readonly selectedSectionId = signal<string | null>(null);
  readonly chunkOffset = signal(0);
  readonly hasMoreChunks = signal(false);
  readonly activeTab = signal(0);

  readonly selectedChunkId = signal<string | null>(null);
  readonly selectedStatBlockChunkId = signal<string | null>(null);

  private chunkRequestGeneration = 0;

  constructor() {
    this.loadDocument();
    this.syncSelectionFromRoute();

    this.router.events
      .pipe(
        filter((event) => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.syncSelectionFromRoute());
  }

  private loadDocument(): void {
    const documentId = this.documentId;
    this.api.listSections(documentId).subscribe({
      next: (sections) => {
        this.sectionTree.set(buildSectionTree(sections));
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Document introuvable.');
        this.loading.set(false);
      },
    });
    this.loadChunks(true);
    this.api.listStatBlocks(documentId).subscribe({
      next: (blocks) => this.statBlocks.set(blocks),
      error: () => this.statBlocks.set([]),
    });
  }

  private syncSelectionFromRoute(): void {
    const child = this.route.firstChild;
    if (!child) {
      this.selectedChunkId.set(null);
      this.selectedStatBlockChunkId.set(null);
      return;
    }
    const chunkId = child.snapshot.paramMap.get('chunkId');
    const statBlockId = child.snapshot.paramMap.get('statBlockId');
    if (chunkId) {
      this.selectedChunkId.set(chunkId);
      this.selectedStatBlockChunkId.set(null);
      this.activeTab.set(0);
    } else if (statBlockId) {
      this.selectedStatBlockChunkId.set(statBlockId);
      this.selectedChunkId.set(null);
      this.activeTab.set(1);
    } else {
      this.selectedChunkId.set(null);
      this.selectedStatBlockChunkId.set(null);
    }
  }

  onSectionSelected(sectionId: string | null): void {
    this.selectedSectionId.set(sectionId);
    this.loadChunks(true);
  }

  onChunkSelected(chunkId: string): void {
    void this.router.navigate(['/documents', this.documentId, 'chunks', chunkId]);
  }

  onStatBlockSelected(chunkId: string): void {
    void this.router.navigate(['/documents', this.documentId, 'stat-blocks', chunkId]);
  }

  loadMoreChunks(): void {
    this.loadChunks(false);
  }

  openPdfViewer(): void {
    this.pdfViewer.open(this.documentId);
  }

  private loadChunks(reset: boolean): void {
    if (reset) {
      this.chunkRequestGeneration += 1;
    }
    const generation = this.chunkRequestGeneration;
    const offset = reset ? 0 : this.chunkOffset();

    this.api
      .listChunks(this.documentId, {
        sectionId: this.selectedSectionId() ?? undefined,
        limit: CHUNK_PAGE_SIZE,
        offset,
      })
      .subscribe({
        next: (items) => {
          if (generation !== this.chunkRequestGeneration) {
            return;
          }
          if (reset) {
            this.chunks.set(items);
            this.chunkOffset.set(items.length);
          } else {
            this.chunks.update((current) => [...current, ...items]);
            this.chunkOffset.update((value) => value + items.length);
          }
          this.hasMoreChunks.set(items.length === CHUNK_PAGE_SIZE);
        },
      });
  }
}
