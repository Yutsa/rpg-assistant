import {
  Component,
  computed,
  effect,
  input,
  signal,
} from '@angular/core';
import { PageBlock } from '../../../core/models/campaign.models';
import { mapBlocksToOverlay } from './bbox-overlay.util';

@Component({
  selector: 'app-extractor-pane',
  imports: [],
  templateUrl: './extractor-pane.component.html',
  styleUrl: './extractor-pane.component.scss',
})
export class ExtractorPaneComponent {
  readonly title = input.required<string>();
  readonly subtitle = input.required<string>();
  readonly blocks = input.required<PageBlock[]>();
  readonly pageWidth = input.required<number>();
  readonly pageHeight = input.required<number>();
  readonly renderUrl = input.required<string>();
  readonly strokeColor = input('#1976d2');

  readonly displayWidth = signal(0);
  readonly displayHeight = signal(0);

  readonly overlayBlocks = computed(() =>
    mapBlocksToOverlay(
      this.blocks(),
      this.pageWidth(),
      this.pageHeight(),
      this.displayWidth(),
      this.displayHeight(),
    ),
  );

  constructor() {
    effect(() => {
      this.renderUrl();
      this.displayWidth.set(0);
      this.displayHeight.set(0);
    });
  }

  onImageLoad(event: Event): void {
    const image = event.target as HTMLImageElement;
    this.displayWidth.set(image.clientWidth);
    this.displayHeight.set(image.clientHeight);
  }
}
