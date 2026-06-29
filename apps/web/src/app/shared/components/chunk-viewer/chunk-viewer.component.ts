import { Component, computed, inject, input } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { PdfViewerService } from '../../../core/services/pdf-viewer.service';
import { Chunk } from '../../../core/models/campaign.models';
import { PageRangeBadgeComponent } from '../page-range-badge/page-range-badge.component';

@Component({
  selector: 'app-chunk-viewer',
  imports: [MatButtonModule, MatIconModule, PageRangeBadgeComponent],
  templateUrl: './chunk-viewer.component.html',
  styleUrl: './chunk-viewer.component.scss',
})
export class ChunkViewerComponent {
  readonly pdfViewer = inject(PdfViewerService);

  readonly chunk = input.required<Chunk>();

  readonly paragraphs = computed(() =>
    this.chunk()
      .text.split('\n\n')
      .filter((part) => Boolean(part)),
  );

  openPdf(): void {
    this.pdfViewer.open(this.chunk().document_id, this.chunk().page_start);
  }
}
