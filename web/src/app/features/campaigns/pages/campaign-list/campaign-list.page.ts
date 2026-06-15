import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';
import { Campaign } from '../../../../core/models/campaign.models';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';

@Component({
  selector: 'app-campaign-list-page',
  imports: [RouterLink, MatCardModule, MatProgressSpinnerModule, EmptyStateComponent],
  templateUrl: './campaign-list.page.html',
  styleUrl: './campaign-list.page.scss',
})
export class CampaignListPage {
  private readonly api = inject(CampaignApiService);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly campaigns = signal<Campaign[]>([]);

  constructor() {
    this.api.listCampaigns().subscribe({
      next: (campaigns) => {
        this.campaigns.set(campaigns);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Impossible de charger les campagnes.');
        this.loading.set(false);
      },
    });
  }
}
