import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { catchError, map, of, switchMap, tap } from 'rxjs';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';
import { StatBlockDetail, StatBlockIndex } from '../../../../core/models/campaign.models';
import { decodeStatBlockName, encodeStatBlockName } from '../../../../core/utils/stat-block-route';
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
  private readonly router = inject(Router);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly statBlock = signal<StatBlockDetail | null>(null);
  readonly candidates = signal<StatBlockIndex[]>([]);

  constructor() {
    this.route.paramMap
      .pipe(
        map((params) => ({
          documentId: this.route.parent?.snapshot.paramMap.get('documentId') ?? '',
          name: decodeStatBlockName(params.get('name') ?? ''),
        })),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
          this.candidates.set([]);
        }),
        switchMap(({ documentId, name }) =>
          this.api.getStatBlock(documentId, name).pipe(
            map((detail) => ({ detail, error: null as string | null, candidates: [] as StatBlockIndex[] })),
            catchError((err: HttpErrorResponse) => {
              const body = err.error as { candidates?: StatBlockIndex[] } | undefined;
              if (err.status === 422 && body?.candidates) {
                return of({
                  detail: null,
                  error: 'Plusieurs fiches correspondent à ce nom.',
                  candidates: body.candidates,
                });
              }
              return of({ detail: null, error: 'Fiche introuvable.', candidates: [] });
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe(({ detail, error, candidates }) => {
        this.statBlock.set(detail);
        this.error.set(error);
        this.candidates.set(candidates);
        this.loading.set(false);
      });
  }

  selectCandidate(name: string): void {
    const documentId = this.route.parent?.snapshot.paramMap.get('documentId') ?? '';
    void this.router.navigate([
      '/documents',
      documentId,
      'stat-blocks',
      encodeStatBlockName(name),
    ]);
  }
}
