import { Component, effect, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Router, RouterLink } from '@angular/router';

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

  readonly documentId = input.required<string>();
  readonly pageNumber = input.required<number>();

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly comparison = signal<PageExtractorsCompare | null>(null);

  constructor() {
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
    void this.router.navigate([
      '/documents',
      this.documentId(),
      'pages',
      page,
      'compare-extractors',
    ]);
  }

  private loadComparison(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.getPageExtractorsCompare(this.documentId(), this.pageNumber()).subscribe({
      next: (payload) => {
        this.comparison.set(payload);
        this.loading.set(false);
      },
      error: () => {
        this.error.set(
          'Comparaison indisponible. Vérifiez que le PDF source et Clojure sont accessibles.',
        );
        this.loading.set(false);
      },
    });
  }

  renderUrl(): string {
    return this.api.getPageRenderUrl(this.documentId(), this.pageNumber(), 120);
  }
}
