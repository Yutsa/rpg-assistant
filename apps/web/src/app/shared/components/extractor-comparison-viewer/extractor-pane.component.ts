import {
  Component,
  ElementRef,
  computed,
  effect,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { MatTooltipModule } from '@angular/material/tooltip';
import { PageBlock } from '../../../core/models/campaign.models';
import { mapBlocksToOverlay, OverlayBlock } from './bbox-overlay.util';

@Component({
  selector: 'app-extractor-pane',
  imports: [MatTooltipModule],
  templateUrl: './extractor-pane.component.html',
  styleUrl: './extractor-pane.component.scss',
})
export class ExtractorPaneComponent {
  private readonly canvasWrap = viewChild<ElementRef<HTMLElement>>('canvasWrap');
  private resizeObserver: ResizeObserver | null = null;

  readonly title = input.required<string>();
  readonly subtitle = input.required<string>();
  readonly blocks = input.required<PageBlock[]>();
  readonly pageWidth = input.required<number>();
  readonly pageHeight = input.required<number>();
  readonly renderUrl = input.required<string>();
  readonly strokeColor = input('#1976d2');
  readonly zoom = input(1);
  readonly selectedBlockId = input<string | null>(null);
  readonly hoveredBlockId = input<string | null>(null);
  readonly matchedBlockId = input<string | null>(null);

  readonly blockSelect = output<PageBlock>();
  readonly blockHover = output<PageBlock | null>();

  readonly naturalWidth = signal(0);
  readonly naturalHeight = signal(0);
  readonly containerWidth = signal(0);
  readonly containerHeight = signal(0);

  readonly baseScale = computed(() => {
    const naturalWidth = this.naturalWidth();
    const naturalHeight = this.naturalHeight();
    const containerWidth = this.containerWidth();
    const containerHeight = this.containerHeight();
    if (!naturalWidth || !naturalHeight || !containerWidth) {
      return 0;
    }
    const widthScale = containerWidth / naturalWidth;
    if (containerHeight <= 0) {
      return widthScale;
    }
    return Math.min(widthScale, containerHeight / naturalHeight);
  });

  readonly displayWidth = computed(() => {
    const naturalWidth = this.naturalWidth();
    const baseScale = this.baseScale();
    if (!naturalWidth || !baseScale) {
      return 0;
    }
    return naturalWidth * baseScale * this.zoom();
  });

  readonly displayHeight = computed(() => {
    const naturalHeight = this.naturalHeight();
    const baseScale = this.baseScale();
    if (!naturalHeight || !baseScale) {
      return 0;
    }
    return naturalHeight * baseScale * this.zoom();
  });

  readonly allowScroll = computed(() => this.zoom() > 1);

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
    });

    effect(() => {
      this.zoom();
      queueMicrotask(() => this.observeCanvasWrap());
    });
  }

  onImageLoad(event: Event): void {
    const image = event.target as HTMLImageElement;
    this.naturalWidth.set(image.naturalWidth);
    this.naturalHeight.set(image.naturalHeight);
    this.observeCanvasWrap();
  }

  observeCanvasWrap(): void {
    const element = this.canvasWrap()?.nativeElement;
    if (!element) {
      return;
    }
    this.resizeObserver?.disconnect();
    this.resizeObserver = new ResizeObserver(() => {
      this.updateContainerSize();
    });
    this.resizeObserver.observe(element);
    this.updateContainerSize();
  }

  private updateContainerSize(): void {
    const element = this.canvasWrap()?.nativeElement;
    if (!element) {
      return;
    }
    const styles = getComputedStyle(element);
    const paddingX =
      parseFloat(styles.paddingLeft) + parseFloat(styles.paddingRight);
    const paddingY =
      parseFloat(styles.paddingTop) + parseFloat(styles.paddingBottom);
    const measuredWidth = Math.max(0, element.clientWidth - paddingX);
    const measuredHeight = Math.max(0, element.clientHeight - paddingY);
    if (measuredWidth > 0) {
      this.containerWidth.set(measuredWidth);
    }
    if (measuredHeight > 0) {
      this.containerHeight.set(measuredHeight);
    }
  }

  blockTooltip(block: OverlayBlock): string {
    const parts = [block.id];
    if (block.text) {
      parts.push(block.text.slice(0, 120));
    }
    return parts.join('\n');
  }

  onBlockClick(block: OverlayBlock): void {
    this.blockSelect.emit(block);
  }

  onBlockHover(block: OverlayBlock | null): void {
    this.blockHover.emit(block);
  }
}
