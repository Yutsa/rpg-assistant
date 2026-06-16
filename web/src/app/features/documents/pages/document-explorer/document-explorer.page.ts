import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter, map } from 'rxjs';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTabsModule } from '@angular/material/tabs';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';
import { ChunkListItem, SectionNode, StatBlockIndex } from '../../../../core/models/campaign.models';
import { buildSectionTree } from '../../../../core/utils/section-tree';
import { decodeStatBlockName, encodeStatBlockName } from '../../../../core/utils/stat-block-route';
import { ChunkListComponent } from '../../../../shared/components/chunk-list/chunk-list.component';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { SectionTreeComponent } from '../../../../shared/components/section-tree/section-tree.component';
import { StatBlockListComponent } from '../../../../shared/components/stat-block-list/stat-block-list.component';

const CHUNK_PAGE_SIZE = 20;

@Component({
  selector: 'app-document-explorer-page',
  imports: [
    RouterOutlet,
    MatTabsModule,
    MatProgressSpinnerModule,
    SectionTreeComponent,
    ChunkListComponent,
    StatBlockListComponent,
    EmptyStateComponent,
  ],
  templateUrl: './document-explorer.page.html',
  styleUrl: './document-explorer.page.scss',
})
export class DocumentExplorerPage {
  private readonly api = inject(CampaignApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

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
  readonly selectedStatBlockName = signal<string | null>(null);

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
      this.selectedStatBlockName.set(null);
      return;
    }
    const chunkId = child.snapshot.paramMap.get('chunkId');
    const statName = child.snapshot.paramMap.get('name');
    if (chunkId) {
      this.selectedChunkId.set(chunkId);
      this.selectedStatBlockName.set(null);
      this.activeTab.set(0);
    } else if (statName) {
      this.selectedStatBlockName.set(decodeStatBlockName(statName));
      this.selectedChunkId.set(null);
      this.activeTab.set(1);
    }
  }

  onSectionSelected(sectionId: string | null): void {
    this.selectedSectionId.set(sectionId);
    this.loadChunks(true);
  }

  onChunkSelected(chunkId: string): void {
    void this.router.navigate(['/documents', this.documentId, 'chunks', chunkId]);
  }

  onStatBlockSelected(name: string): void {
    void this.router.navigate([
      '/documents',
      this.documentId,
      'stat-blocks',
      encodeStatBlockName(name),
    ]);
  }

  loadMoreChunks(): void {
    this.loadChunks(false);
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
