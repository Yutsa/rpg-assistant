import { Component, input } from '@angular/core';

import { Chunk } from '../../../core/models/campaign.models';
import { PageRangeBadgeComponent } from '../page-range-badge/page-range-badge.component';

@Component({
  selector: 'app-chunk-viewer',
  imports: [PageRangeBadgeComponent],
  templateUrl: './chunk-viewer.component.html',
  styleUrl: './chunk-viewer.component.scss',
})
export class ChunkViewerComponent {
  readonly chunk = input.required<Chunk>();
}
