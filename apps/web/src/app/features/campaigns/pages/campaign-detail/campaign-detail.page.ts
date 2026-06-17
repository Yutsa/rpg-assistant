import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { catchError, map, of, switchMap, tap } from 'rxjs';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';
import { CampaignSummary, Document } from '../../../../core/models/campaign.models';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';

@Component({
  selector: 'app-campaign-detail-page',
  imports: [RouterLink, MatCardModule, MatProgressSpinnerModule, EmptyStateComponent],
  templateUrl: './campaign-detail.page.html',
  styleUrl: './campaign-detail.page.scss',
})
export class CampaignDetailPage {
  private readonly api = inject(CampaignApiService);
  private readonly route = inject(ActivatedRoute);

  readonly campaignId = signal('');
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly documents = signal<Document[]>([]);
  readonly summary = signal<CampaignSummary | null>(null);

  constructor() {
    this.route.paramMap
      .pipe(
        map((params) => params.get('campaignId') ?? ''),
        tap((campaignId) => {
          this.campaignId.set(campaignId);
          this.loading.set(true);
          this.error.set(null);
          this.documents.set([]);
          this.summary.set(null);
        }),
        switchMap((campaignId) =>
          this.api.listDocuments(campaignId).pipe(
            map((documents) => ({ documents, error: null as string | null })),
            catchError(() => of({ documents: [], error: 'Campagne introuvable.' })),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe(({ documents, error }) => {
        this.documents.set(documents);
        this.error.set(error);
        this.loading.set(false);
      });

    this.route.paramMap
      .pipe(
        map((params) => params.get('campaignId') ?? ''),
        switchMap((campaignId) =>
          this.api.getCampaignSummary(campaignId).pipe(catchError(() => of(null))),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((summary) => this.summary.set(summary));
  }
}
