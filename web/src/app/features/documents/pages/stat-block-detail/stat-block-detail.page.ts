import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';
import { StatBlockDetail, StatBlockIndex } from '../../../../core/models/campaign.models';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { StatBlockViewerComponent } from '../../../../shared/components/stat-block-viewer/stat-block-viewer.component';

@Component({
  selector: 'app-stat-block-detail-page',
  imports: [
    MatButtonModule,
    MatProgressSpinnerModule,
    StatBlockViewerComponent,
    EmptyStateComponent,
  ],
  templateUrl: './stat-block-detail.page.html',
  styleUrl: './stat-block-detail.page.scss',
})
export class StatBlockDetailPage {
  private readonly api = inject(CampaignApiService);
  private readonly route = inject(ActivatedRoute);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly statBlock = signal<StatBlockDetail | null>(null);
  readonly candidates = signal<StatBlockIndex[]>([]);

  constructor() {
    const documentId = this.route.parent?.snapshot.paramMap.get('documentId') ?? '';
    const name = decodeURIComponent(this.route.snapshot.paramMap.get('name') ?? '');
    this.loadStatBlock(documentId, name);
  }

  selectCandidate(name: string): void {
    const documentId = this.route.parent?.snapshot.paramMap.get('documentId') ?? '';
    this.candidates.set([]);
    this.loading.set(true);
    this.loadStatBlock(documentId, name);
  }

  private loadStatBlock(documentId: string, name: string): void {
    this.api.getStatBlock(documentId, name).subscribe({
      next: (detail) => {
        this.statBlock.set(detail);
        this.loading.set(false);
      },
      error: (err) => {
        const body = err.error;
        if (err.status === 422 && body?.candidates) {
          this.candidates.set(body.candidates);
          this.error.set('Plusieurs fiches correspondent à ce nom.');
        } else {
          this.error.set('Fiche introuvable.');
        }
        this.loading.set(false);
      },
    });
  }
}
