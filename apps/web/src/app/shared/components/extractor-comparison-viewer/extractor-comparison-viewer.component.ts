import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, effect, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { CampaignApiService } from '../../../core/services/campaign-api.service';
import { PageExtractorsCompare } from '../../../core/models/campaign.models';
import { EmptyStateComponent } from '../empty-state/empty-state.component';
import { ExtractorPaneComponent } from './extractor-pane.component';

@Component({
  selector: 'app-extractor-comparison-viewer',
  imports: [
    RouterLink,
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
