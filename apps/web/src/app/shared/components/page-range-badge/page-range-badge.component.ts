import { Component, input } from '@angular/core';

@Component({
  selector: 'app-page-range-badge',
  templateUrl: './page-range-badge.component.html',
  styleUrl: './page-range-badge.component.scss',
})
export class PageRangeBadgeComponent {
  readonly pageStart = input.required<number>();
  readonly pageEnd = input.required<number>();
}
