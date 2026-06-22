import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { map, tap } from 'rxjs';

import { ExtractorComparisonViewerComponent } from '../../../../shared/components/extractor-comparison-viewer/extractor-comparison-viewer.component';

@Component({
  selector: 'app-page-extractor-comparison-page',
  imports: [ExtractorComparisonViewerComponent],
  template: `
    <app-extractor-comparison-viewer
      [documentId]="documentId"
      [pageNumber]="pageNumber()"
    />
  `,
})
export class PageExtractorComparisonPage {
  private readonly route = inject(ActivatedRoute);

  readonly documentId = this.route.snapshot.paramMap.get('documentId') ?? '';
  readonly pageNumber = signal(1);

  constructor() {
    this.route.paramMap
      .pipe(
        map((params) => Number(params.get('pageNumber') ?? '1')),
        tap((pageNumber) => this.pageNumber.set(pageNumber)),
        takeUntilDestroyed(),
      )
      .subscribe();
  }
}
