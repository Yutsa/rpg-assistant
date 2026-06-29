import { Component, input, output } from '@angular/core';

@Component({
  selector: 'app-page-range-badge',
  templateUrl: './page-range-badge.component.html',
  styleUrl: './page-range-badge.component.scss',
})
export class PageRangeBadgeComponent {
  readonly pageStart = input.required<number>();
  readonly pageEnd = input.required<number>();
  readonly actionable = input(false);
  readonly pageClick = output<void>();

  onClick(event: Event): void {
    event.stopPropagation();
    event.preventDefault();
    this.pageClick.emit();
  }
}
