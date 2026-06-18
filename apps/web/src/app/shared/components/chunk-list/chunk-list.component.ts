import { Component, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import { ChunkListItem } from '../../../core/models/campaign.models';
import { PageRangeBadgeComponent } from '../page-range-badge/page-range-badge.component';

@Component({
  selector: 'app-chunk-list',
  imports: [MatButtonModule, PageRangeBadgeComponent],
  templateUrl: './chunk-list.component.html',
  styleUrl: './chunk-list.component.scss',
})
export class ChunkListComponent {
  readonly chunks = input.required<ChunkListItem[]>();
  readonly selectedChunkId = input<string | null>(null);
  readonly hasMore = input(false);
  readonly chunkSelected = output<string>();
  readonly loadMore = output<void>();
}
