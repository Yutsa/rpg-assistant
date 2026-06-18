import { Component, input, output } from '@angular/core';
import { MatListModule } from '@angular/material/list';

import { StatBlockIndex } from '../../../core/models/campaign.models';
import { PageRangeBadgeComponent } from '../page-range-badge/page-range-badge.component';

@Component({
  selector: 'app-stat-block-list',
  imports: [MatListModule, PageRangeBadgeComponent],
  templateUrl: './stat-block-list.component.html',
  styleUrl: './stat-block-list.component.scss',
})
export class StatBlockListComponent {
  readonly statBlocks = input.required<StatBlockIndex[]>();
  readonly selectedChunkId = input<string | null>(null);
  readonly sectionTitles = input<Record<string, string>>({});
  readonly statBlockSelected = output<string>();

  sectionTitle(sectionId: string | null): string | null {
    if (!sectionId) {
      return null;
    }
    return this.sectionTitles()[sectionId] ?? null;
  }
}
