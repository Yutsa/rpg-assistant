import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { catchError, map, of, switchMap, tap } from 'rxjs';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';
import { CampaignSummary, Document } from '../../../../core/models/campaign.models';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import {
  DeleteCampaignDialogComponent,
  DeleteCampaignDialogData,
} from '../../dialogs/delete-campaign-dialog/delete-campaign-dialog.component';

@Component({
  selector: 'app-campaign-detail-page',
  imports: [
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    EmptyStateComponent,
  ],
  templateUrl: './campaign-detail.page.html',
  styleUrl: './campaign-detail.page.scss',
})
export class CampaignDetailPage {
  private readonly api = inject(CampaignApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);

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

  openDeleteDialog(): void {
    const campaignId = this.campaignId();
    const summary = this.summary();
    const data: DeleteCampaignDialogData = {
      campaignId,
      campaignTitle: campaignId,
      documentCount: summary?.document_count ?? this.documents().length,
    };
    this.dialog
      .open(DeleteCampaignDialogComponent, {
        width: '480px',
        data,
      })
      .afterClosed()
      .subscribe((deleted) => {
        if (deleted) {
          void this.router.navigate(['/campaigns']);
        }
      });
  }
}
