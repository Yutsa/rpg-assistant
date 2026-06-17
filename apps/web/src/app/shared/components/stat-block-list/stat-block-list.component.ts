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
  readonly selectedName = input<string | null>(null);
  readonly statBlockSelected = output<string>();
}
