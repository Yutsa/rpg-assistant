import { KeyValuePipe } from '@angular/common';
import { Component, computed, inject, input } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { StatBlockDetail } from '../../../core/models/campaign.models';
import { PdfViewerService } from '../../../core/services/pdf-viewer.service';
import { PageRangeBadgeComponent } from '../page-range-badge/page-range-badge.component';

@Component({
  selector: 'app-stat-block-viewer',
  imports: [KeyValuePipe, MatButtonModule, MatIconModule, PageRangeBadgeComponent],
  templateUrl: './stat-block-viewer.component.html',
  styleUrl: './stat-block-viewer.component.scss',
})
export class StatBlockViewerComponent {
  private readonly pdfViewer = inject(PdfViewerService);

  readonly statBlock = input.required<StatBlockDetail>();

  readonly documentId = computed(
    () => this.statBlock().source_refs?.[0]?.document_id ?? '',
  );

  readonly hasCombatStats = computed(() => {
    const block = this.statBlock();
    return (
      block.defense != null ||
      block.vigor != null ||
      block.initiative != null ||
      block.mana != null
    );
  });

  readonly showBodyText = computed(() => {
    const block = this.statBlock();
    const hasStructuredStats =
      block.nc != null ||
      this.hasCombatStats() ||
      (block.attributes != null && Object.keys(block.attributes).length > 0) ||
      (block.attacks?.length ?? 0) > 0 ||
      (block.abilities?.length ?? 0) > 0;
    return !hasStructuredStats && !!this.bodyText();
  });

  readonly bodyText = computed(() => {
    const text = this.statBlock().text?.trim();
    if (!text) {
      return '';
    }
    const name = this.statBlock().name?.trim();
    if (!name) {
      return text;
    }
    const withoutTitle = text.startsWith(name)
      ? text.slice(name.length).trim()
      : text;
    return withoutTitle.replace(/^\n+/, '').trim();
  });

  openPdf(): void {
    const documentId = this.documentId();
    if (!documentId) {
      return;
    }
    this.pdfViewer.open(documentId, this.statBlock().pages.start);
  }
}
