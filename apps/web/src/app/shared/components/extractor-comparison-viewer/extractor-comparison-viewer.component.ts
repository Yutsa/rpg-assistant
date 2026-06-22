import { DecimalPipe, JsonPipe, KeyValuePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, effect, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { CampaignApiService } from '../../../core/services/campaign-api.service';
import { PageBlock, PageExtractorsCompare } from '../../../core/models/campaign.models';
import { EmptyStateComponent } from '../empty-state/empty-state.component';
import {
  BlockSelection,
  CompareLane,
  findBestMatchBlock,
} from './bbox-overlay.util';
import { ExtractorPaneComponent } from './extractor-pane.component';

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;
const ZOOM_STEP = 0.25;

@Component({
  selector: 'app-extractor-comparison-viewer',
  imports: [
    RouterLink,
    DecimalPipe,
    JsonPipe,
    KeyValuePipe,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    EmptyStateComponent,
    ExtractorPaneComponent,
  ],
  templateUrl: './extractor-comparison-viewer.component.html',
  styleUrl: './extractor-comparison-viewer.component.scss',
})
export class ExtractorComparisonViewerComponent {
  private readonly api = inject(CampaignApiService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly documentId = input.required<string>();
  readonly pageNumber = input.required<number>();

  readonly loading = signal(false);
  readonly refreshing = signal(false);
  readonly error = signal<string | null>(null);
  readonly comparison = signal<PageExtractorsCompare | null>(null);
  readonly zoom = signal(1);
  readonly selection = signal<BlockSelection | null>(null);
  readonly hoveredBlockId = signal<string | null>(null);
  readonly detailOpen = signal(false);
  readonly detailExpanded = signal(false);

  readonly matchedBlock = computed(() => {
    const data = this.comparison();
    const current = this.selection();
    if (!data || !current) {
      return null;
    }
    const candidates =
      current.lane === 'pymupdf' ? data.pdfbox.blocks : data.pymupdf.blocks;
    return findBestMatchBlock(current.block, candidates);
  });

  readonly pymupdfSelectedId = computed(() => {
    const selection = this.selection();
    return selection?.lane === 'pymupdf' ? selection.block.id : null;
  });

  readonly pdfboxSelectedId = computed(() => {
    const selection = this.selection();
    return selection?.lane === 'pdfbox' ? selection.block.id : null;
  });

  readonly pymupdfMatchedId = computed(() => {
    const data = this.comparison();
    if (!data) {
      return null;
    }
    const selection = this.selection();
    if (selection?.lane === 'pdfbox') {
      return findBestMatchBlock(selection.block, data.pymupdf.blocks)?.id ?? null;
    }
    const hovered = this.hoveredBlockId();
    const pdfboxBlock = data.pdfbox.blocks.find((block) => block.id === hovered);
    if (pdfboxBlock) {
      return findBestMatchBlock(pdfboxBlock, data.pymupdf.blocks)?.id ?? null;
    }
    return null;
  });

  readonly pdfboxMatchedId = computed(() => {
    const data = this.comparison();
    if (!data) {
      return null;
    }
    const selection = this.selection();
    if (selection?.lane === 'pymupdf') {
      return findBestMatchBlock(selection.block, data.pdfbox.blocks)?.id ?? null;
    }
    const hovered = this.hoveredBlockId();
    const pymupdfBlock = data.pymupdf.blocks.find((block) => block.id === hovered);
    if (pymupdfBlock) {
      return findBestMatchBlock(pymupdfBlock, data.pdfbox.blocks)?.id ?? null;
    }
    return null;
  });

  private readonly pageCache = new Map<number, PageExtractorsCompare>();
  private readonly prefetchSubscriptions = new Map<number, Subscription>();
  private loadRequestId = 0;

  constructor() {
    effect(() => {
      this.documentId();
      this.pageCache.clear();
      this.prefetchSubscriptions.forEach((subscription) => subscription.unsubscribe());
      this.prefetchSubscriptions.clear();
    });

    effect(() => {
      this.documentId();
      this.pageNumber();
      this.clearInteractionState();
      this.loadComparison();
    });
  }

  goToPage(page: number): void {
    if (page < 1) {
      return;
    }
    void this.router.navigate(
      ['/documents', this.documentId(), 'pages', page, 'compare-extractors'],
      { replaceUrl: true },
    );
  }

  renderUrl(): string {
    return this.api.getPageRenderUrl(this.documentId(), this.pageNumber(), 120);
  }

  zoomIn(): void {
    this.zoom.update((value) => Math.min(MAX_ZOOM, value + ZOOM_STEP));
  }

  zoomOut(): void {
    this.zoom.update((value) => Math.max(MIN_ZOOM, value - ZOOM_STEP));
  }

  resetZoom(): void {
    this.zoom.set(1);
  }

  selectBlock(lane: CompareLane, block: PageBlock): void {
    this.selection.set({ lane, block });
    this.detailOpen.set(true);
    this.detailExpanded.set(false);
  }

  onBlockHover(block: PageBlock | null): void {
    this.hoveredBlockId.set(block?.id ?? null);
  }

  closeDetail(): void {
    this.detailOpen.set(false);
    this.detailExpanded.set(false);
  }

  toggleDetailExpanded(): void {
    this.detailExpanded.update((value) => !value);
  }

  laneLabel(lane: CompareLane): string {
    return lane === 'pymupdf' ? 'PyMuPDF' : 'PDFBox';
  }

  private clearInteractionState(): void {
    this.selection.set(null);
    this.hoveredBlockId.set(null);
    this.detailOpen.set(false);
    this.detailExpanded.set(false);
    this.zoom.set(1);
  }

  private loadComparison(): void {
    const page = this.pageNumber();
    const documentId = this.documentId();
    const cached = this.pageCache.get(page);

    if (cached) {
      this.comparison.set(cached);
      this.loading.set(false);
      this.error.set(null);
      this.prefetchAdjacentPages(documentId, page);
      return;
    }

    this.loading.set(this.comparison() === null);
    this.refreshing.set(this.comparison() !== null);
    this.error.set(null);

    const requestId = ++this.loadRequestId;
    this.api
      .getPageExtractorsCompare(documentId, page)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (payload) => {
          if (requestId !== this.loadRequestId) {
            return;
          }
          this.pageCache.set(page, payload);
          this.comparison.set(payload);
          this.loading.set(false);
          this.refreshing.set(false);
          this.prefetchAdjacentPages(documentId, page);
        },
        error: (err: HttpErrorResponse) => {
          if (requestId !== this.loadRequestId) {
            return;
          }
          const detail =
            typeof err.error?.detail === 'string'
              ? err.error.detail
              : typeof err.error?.error === 'string'
                ? err.error.error
                : null;
          const suffix = detail
            ? ` (${err.status}: ${detail})`
            : err.status
              ? ` (HTTP ${err.status})`
              : '';
          this.error.set(
            `Comparaison indisponible. Vérifiez que l'API est à jour, que le PDF source et Clojure CLI sont accessibles${suffix}.`,
          );
          this.loading.set(false);
          this.refreshing.set(false);
        },
      });
  }

  private prefetchAdjacentPages(documentId: string, page: number): void {
    this.prefetchPage(documentId, page - 1);
    this.prefetchPage(documentId, page + 1);
  }

  private prefetchPage(documentId: string, page: number): void {
    if (page < 1 || this.pageCache.has(page) || this.prefetchSubscriptions.has(page)) {
      return;
    }

    const subscription = this.api.getPageExtractorsCompare(documentId, page).subscribe({
      next: (payload) => {
        this.pageCache.set(page, payload);
        this.prefetchSubscriptions.delete(page);
      },
      error: () => {
        this.prefetchSubscriptions.delete(page);
      },
    });
    this.prefetchSubscriptions.set(page, subscription);
  }
}
