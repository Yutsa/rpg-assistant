import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';
import { Campaign } from '../../../../core/models/campaign.models';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { ImportCampaignDialogComponent } from '../../dialogs/import-campaign-dialog/import-campaign-dialog.component';

@Component({
  selector: 'app-campaign-list-page',
  imports: [
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    EmptyStateComponent,
  ],
  templateUrl: './campaign-list.page.html',
  styleUrl: './campaign-list.page.scss',
})
export class CampaignListPage {
  private readonly api = inject(CampaignApiService);
  private readonly dialog = inject(MatDialog);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly campaigns = signal<Campaign[]>([]);

  constructor() {
    this.reloadCampaigns();
  }

  openImportDialog(): void {
    this.dialog
      .open(ImportCampaignDialogComponent, {
        width: '560px',
        disableClose: true,
      })
      .afterClosed()
      .subscribe(() => this.reloadCampaigns());
  }

  private reloadCampaigns(): void {
    this.loading.set(true);
    this.error.set(null);
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
