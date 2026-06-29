import { Component, inject, input, output } from '@angular/core';
import { MatListModule } from '@angular/material/list';

import { PdfViewerService } from '../../../core/services/pdf-viewer.service';
import { StatBlockIndex } from '../../../core/models/campaign.models';
import { PageRangeBadgeComponent } from '../page-range-badge/page-range-badge.component';

@Component({
  selector: 'app-stat-block-list',
  imports: [MatListModule, PageRangeBadgeComponent],
  templateUrl: './stat-block-list.component.html',
  styleUrl: './stat-block-list.component.scss',
})
export class StatBlockListComponent {
  private readonly pdfViewer = inject(PdfViewerService);

  readonly documentId = input.required<string>();
  readonly statBlocks = input.required<StatBlockIndex[]>();
  readonly selectedChunkId = input<string | null>(null);
  readonly statBlockSelected = output<string>();

  openPdfAtPage(pageNumber: number, event?: Event): void {
    event?.stopPropagation();
    this.pdfViewer.open(this.documentId(), pageNumber);
  }
}
