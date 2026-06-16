import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { catchError, map, of, switchMap, tap } from 'rxjs';

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
    this.route.paramMap
      .pipe(
        map((params) => params.get('chunkId') ?? ''),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap((chunkId) =>
          this.api.getChunk(chunkId).pipe(
            map((chunk) => ({ chunk, error: null as string | null })),
            catchError(() => of({ chunk: null, error: 'Chunk introuvable.' })),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe(({ chunk, error }) => {
        this.chunk.set(chunk);
        this.error.set(error);
        this.loading.set(false);
      });
  }
}
