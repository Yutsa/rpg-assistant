import { KeyValuePipe } from '@angular/common';
import { Component, input } from '@angular/core';
import { MatChipsModule } from '@angular/material/chips';

import { StatBlockDetail } from '../../../core/models/campaign.models';
import { PageRangeBadgeComponent } from '../page-range-badge/page-range-badge.component';

@Component({
  selector: 'app-stat-block-viewer',
  imports: [KeyValuePipe, MatChipsModule, PageRangeBadgeComponent],
  templateUrl: './stat-block-viewer.component.html',
  styleUrl: './stat-block-viewer.component.scss',
})
export class StatBlockViewerComponent {
  readonly statBlock = input.required<StatBlockDetail>();
}
