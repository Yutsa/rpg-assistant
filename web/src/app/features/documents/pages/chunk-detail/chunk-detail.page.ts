import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';
import { Chunk } from '../../../../core/models/campaign.models';
import { ChunkViewerComponent } from '../../../../shared/components/chunk-viewer/chunk-viewer.component';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';

@Component({
  selector: 'app-chunk-detail-page',
  imports: [MatProgressSpinnerModule, ChunkViewerComponent, EmptyStateComponent],
  templateUrl: './chunk-detail.page.html',
  styleUrl: './chunk-detail.page.scss',
})
export class ChunkDetailPage {
  private readonly api = inject(CampaignApiService);
  private readonly route = inject(ActivatedRoute);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly chunk = signal<Chunk | null>(null);

  constructor() {
    const chunkId = this.route.snapshot.paramMap.get('chunkId') ?? '';
    this.api.getChunk(chunkId).subscribe({
      next: (chunk) => {
        this.chunk.set(chunk);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Chunk introuvable.');
        this.loading.set(false);
      },
    });
  }
}
