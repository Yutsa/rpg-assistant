import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { map } from 'rxjs';

import { PageLayoutViewerComponent } from '../../../../shared/components/page-layout-viewer/page-layout-viewer.component';

@Component({
  selector: 'app-page-layout-viewer-page',
  imports: [PageLayoutViewerComponent],
  template: `
    <app-page-layout-viewer
      [documentId]="documentId"
      [pageNumber]="pageNumber()"
      (pageNumberChange)="onPageNumberChange($event)"
    />
  `,
})
export class PageLayoutViewerPage {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly documentId = this.route.snapshot.paramMap.get('documentId') ?? '';
  readonly pageNumber = signal(1);

  constructor() {
    this.route.paramMap
      .pipe(
        map((params) => Number(params.get('pageNumber') ?? '1')),
        takeUntilDestroyed(),
      )
      .subscribe((pageNumber) => this.pageNumber.set(pageNumber));
  }

  onPageNumberChange(pageNumber: number): void {
    void this.router.navigate(['/documents', this.documentId, 'pages', pageNumber]);
  }
}
