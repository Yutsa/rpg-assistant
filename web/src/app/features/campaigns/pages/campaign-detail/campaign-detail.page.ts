import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

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

  readonly campaignId = this.route.snapshot.paramMap.get('campaignId') ?? '';
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly documents = signal<Document[]>([]);
  readonly summary = signal<CampaignSummary | null>(null);

  constructor() {
    const campaignId = this.campaignId;
    this.api.listDocuments(campaignId).subscribe({
      next: (documents) => {
        this.documents.set(documents);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Campagne introuvable.');
        this.loading.set(false);
      },
    });
    this.api.getCampaignSummary(campaignId).subscribe({
      next: (summary) => this.summary.set(summary),
      error: () => undefined,
    });
  }
}
