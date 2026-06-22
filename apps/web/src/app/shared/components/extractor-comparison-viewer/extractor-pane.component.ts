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
    effect((onCleanup) => {
      this.renderUrl();
      this.pageWidth();
      this.pageHeight();
      const wrap = this.canvasWrap()?.nativeElement;
      if (!wrap) {
        return;
      }

      const updateSize = () => {
        const pageWidth = this.pageWidth();
        const pageHeight = this.pageHeight();
        if (!pageWidth || !pageHeight) {
          this.displayWidth.set(0);
          this.displayHeight.set(0);
          return;
        }

        const availableWidth = Math.max(0, wrap.clientWidth - 16);
        const scale = availableWidth / pageWidth;
        this.displayWidth.set(availableWidth);
        this.displayHeight.set(pageHeight * scale);
      };

      const observer = new ResizeObserver(() => updateSize());
      observer.observe(wrap);
      updateSize();
      onCleanup(() => observer.disconnect());
    });
  }
}
