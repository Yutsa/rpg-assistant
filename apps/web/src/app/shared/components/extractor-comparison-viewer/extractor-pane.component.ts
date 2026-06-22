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

  readonly displayWidth = computed(() => {
    const naturalWidth = this.naturalWidth();
    const containerWidth = this.containerWidth();
    if (!naturalWidth || !containerWidth) {
      return 0;
    }
    return containerWidth * this.zoom();
  });

  readonly displayHeight = computed(() => {
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
      this.updateContainerWidth();
    });
    this.resizeObserver.observe(element);
    this.updateContainerWidth();
  }

  private updateContainerWidth(): void {
    const element = this.canvasWrap()?.nativeElement;
    if (!element) {
      return;
    }
    const styles = getComputedStyle(element);
    const paddingX =
      parseFloat(styles.paddingLeft) + parseFloat(styles.paddingRight);
    const measured = Math.max(0, element.clientWidth - paddingX);
    if (measured > 0) {
      this.containerWidth.set(measured);
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
