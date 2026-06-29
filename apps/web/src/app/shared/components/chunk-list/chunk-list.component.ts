import { Component, inject, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import { PdfViewerService } from '../../../core/services/pdf-viewer.service';
import { ChunkListItem } from '../../../core/models/campaign.models';
import { PageRangeBadgeComponent } from '../page-range-badge/page-range-badge.component';

@Component({
  selector: 'app-chunk-list',
  imports: [MatButtonModule, PageRangeBadgeComponent],
  templateUrl: './chunk-list.component.html',
  styleUrl: './chunk-list.component.scss',
})
export class ChunkListComponent {
  private readonly pdfViewer = inject(PdfViewerService);

  readonly documentId = input.required<string>();
  readonly chunks = input.required<ChunkListItem[]>();
  readonly selectedChunkId = input<string | null>(null);
  readonly hasMore = input(false);
  readonly chunkSelected = output<string>();
  readonly loadMore = output<void>();

  openPdfAtPage(pageNumber: number): void {
    this.pdfViewer.open(this.documentId(), pageNumber);
  }
}
