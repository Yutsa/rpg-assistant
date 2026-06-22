import {
  Component,
  ElementRef,
  computed,
  effect,
  input,
  signal,
  viewChild,
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

  private readonly canvasWrap = viewChild<ElementRef<HTMLElement>>('canvasWrap');

  readonly naturalWidth = signal(0);
  readonly naturalHeight = signal(0);
  readonly imageRenderWidth = signal(0);
  readonly imageRenderHeight = signal(0);

  readonly displayWidth = computed(() => {
    const rendered = this.imageRenderWidth();
    if (rendered > 0) {
      return rendered;
    }
    const naturalWidth = this.naturalWidth();
    return naturalWidth > 0 ? naturalWidth : 0;
  });

  readonly displayHeight = computed(() => {
    const rendered = this.imageRenderHeight();
    if (rendered > 0) {
      return rendered;
    }
    const naturalWidth = this.naturalWidth();
    const naturalHeight = this.naturalHeight();
    const displayWidth = this.displayWidth();
    if (!naturalWidth || !naturalHeight || !displayWidth) {
      return 0;
    }
    return naturalHeight * (displayWidth / naturalWidth);
  });

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
      this.naturalWidth.set(0);
      this.naturalHeight.set(0);
      this.imageRenderWidth.set(0);
      this.imageRenderHeight.set(0);
    });
  }

  onImageLoad(event: Event): void {
    const image = event.target as HTMLImageElement;
    this.naturalWidth.set(image.naturalWidth);
    this.naturalHeight.set(image.naturalHeight);
    this.imageRenderWidth.set(image.clientWidth);
    this.imageRenderHeight.set(image.clientHeight);
  }
}
