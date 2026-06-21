import {
  Component,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DecimalPipe, JsonPipe, KeyValuePipe } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { catchError, combineLatest, map, of, switchMap, tap } from 'rxjs';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';
import { PageMeta, PageNode } from '../../../../core/models/campaign.models';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';

interface OverlayNode extends PageNode {
  screenX: number;
  screenY: number;
  screenWidth: number;
  screenHeight: number;
}

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;
const ZOOM_STEP = 0.25;

@Component({
  selector: 'app-page-layout-viewer-page',
  imports: [
    RouterLink,
    DecimalPipe,
    JsonPipe,
    KeyValuePipe,
    MatButtonModule,
    MatCheckboxModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    EmptyStateComponent,
  ],
  templateUrl: './page-layout-viewer.page.html',
  styleUrl: './page-layout-viewer.page.scss',
})
export class PageLayoutViewerPage {
  private readonly api = inject(CampaignApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  private readonly canvasWrap = viewChild<ElementRef<HTMLElement>>('canvasWrap');
  private resizeObserver: ResizeObserver | null = null;

  readonly documentId = this.route.snapshot.paramMap.get('documentId') ?? '';
  readonly pageNumber = signal(1);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly pageMeta = signal<PageMeta | null>(null);
  readonly nodes = signal<PageNode[]>([]);
  readonly renderUrl = signal('');
  readonly naturalWidth = signal(0);
  readonly naturalHeight = signal(0);
  readonly containerWidth = signal(0);
  readonly zoom = signal(1);
  readonly hoveredNodeId = signal<string | null>(null);
  readonly selectedNode = signal<PageNode | null>(null);
  readonly detailOpen = signal(false);
  readonly detailExpanded = signal(false);

  readonly showBlocks = signal(true);
  readonly showLines = signal(false);
  readonly showSpans = signal(false);

  readonly displayWidth = computed(() => {
    const nw = this.naturalWidth();
    const cw = this.containerWidth();
    if (!nw || !cw) {
      return 0;
    }
    return cw * this.zoom();
  });

  readonly displayHeight = computed(() => {
    const nw = this.naturalWidth();
    const nh = this.naturalHeight();
    const dw = this.displayWidth();
    if (!nw || !nh || !dw) {
      return 0;
    }
    return nh * (dw / nw);
  });

  readonly overlayNodes = computed(() => {
    const meta = this.pageMeta();
    const imgW = this.displayWidth();
    const imgH = this.displayHeight();
    if (!meta || imgW === 0 || imgH === 0) {
      return [] as OverlayNode[];
    }
    const scaleX = imgW / meta.width;
    const scaleY = imgH / meta.height;
    return this.visibleNodes().map((node) => ({
      ...node,
      screenX: node.bbox.x0 * scaleX,
      screenY: node.bbox.y0 * scaleY,
      screenWidth: (node.bbox.x1 - node.bbox.x0) * scaleX,
      screenHeight: (node.bbox.y1 - node.bbox.y0) * scaleY,
    }));
  });

  readonly visibleNodes = computed(() => {
    const depths = new Set<string>();
    if (this.showBlocks()) {
      depths.add('block');
    }
    if (this.showLines()) {
      depths.add('line');
    }
    if (this.showSpans()) {
      depths.add('span');
    }
    return this.nodes().filter((node) => depths.has(node.depth));
  });

  constructor() {
    this.route.paramMap
      .pipe(
        map((params) => Number(params.get('pageNumber') ?? '1')),
        tap((pageNumber) => {
          this.pageNumber.set(pageNumber);
          this.loading.set(true);
          this.error.set(null);
          this.selectedNode.set(null);
          this.detailOpen.set(false);
          this.detailExpanded.set(false);
          this.hoveredNodeId.set(null);
          this.zoom.set(1);
        }),
        switchMap((pageNumber) =>
          combineLatest([
            this.api.getPageMeta(this.documentId, pageNumber),
            this.api.listPageNodes(this.documentId, pageNumber),
          ]).pipe(
            map(([meta, nodes]) => ({
              meta,
              nodes,
              renderUrl: this.api.getPageRenderUrl(this.documentId, pageNumber, 120),
              error: null as string | null,
            })),
            catchError(() =>
              of({
                meta: null,
                nodes: [] as PageNode[],
                renderUrl: '',
                error:
                  'Layout brut indisponible. Réimportez le PDF avec --ingest-mode layout-only.',
              }),
            ),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe(({ meta, nodes, renderUrl, error }) => {
        this.pageMeta.set(meta);
        this.nodes.set(nodes);
        this.renderUrl.set(renderUrl);
        this.error.set(error);
        this.loading.set(false);
        queueMicrotask(() => this.observeCanvasWrap());
      });
  }

  onImageLoad(event: Event): void {
    const image = event.target as HTMLImageElement;
    this.naturalWidth.set(image.naturalWidth);
    this.naturalHeight.set(image.naturalHeight);
    this.updateContainerWidth();
  }

  observeCanvasWrap(): void {
    const element = this.canvasWrap()?.nativeElement;
    if (!element) {
      return;
    }
    this.resizeObserver?.disconnect();
    this.resizeObserver = new ResizeObserver(() => this.updateContainerWidth());
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
    this.containerWidth.set(Math.max(0, element.clientWidth - paddingX));
  }

  zoomIn(): void {
    this.zoom.update((value) => Math.min(MAX_ZOOM, value + ZOOM_STEP));
  }

  zoomOut(): void {
    this.zoom.update((value) => Math.max(MIN_ZOOM, value - ZOOM_STEP));
  }

  resetZoom(): void {
    this.zoom.set(1);
  }

  nodeClass(node: PageNode): string {
    if (node.node_type === 'image') {
      return 'node-image';
    }
    return `node-${node.depth}`;
  }

  nodeTooltip(node: PageNode): string {
    const parts = [`${node.depth} · ${node.id}`];
    if (node.text) {
      parts.push(node.text.slice(0, 120));
    }
    const font = node.metadata['font'];
    const size = node.metadata['size'];
    if (font || size) {
      parts.push(`${font ?? ''} ${size ?? ''}`.trim());
    }
    return parts.join('\n');
  }

  selectNode(node: PageNode): void {
    this.selectedNode.set(node);
    this.detailOpen.set(true);
    this.detailExpanded.set(false);
    queueMicrotask(() => this.scrollNodeIntoView(node));
  }

  toggleDetailExpanded(): void {
    this.detailExpanded.update((value) => !value);
  }

  closeDetail(): void {
    this.detailOpen.set(false);
    this.detailExpanded.set(false);
  }

  private scrollNodeIntoView(node: PageNode): void {
    const wrap = this.canvasWrap()?.nativeElement;
    if (!wrap) {
      return;
    }
    const overlay = this.overlayNodes().find((entry) => entry.id === node.id);
    if (!overlay) {
      return;
    }
    const stripOffset = 150;
    const nodeTop = overlay.screenY;
    const nodeBottom = overlay.screenY + overlay.screenHeight;
    const viewTop = wrap.scrollTop;
    const viewBottom = wrap.scrollTop + wrap.clientHeight - stripOffset;

    if (nodeBottom > viewBottom) {
      wrap.scrollTop = nodeBottom - wrap.clientHeight + stripOffset + 12;
    } else if (nodeTop < viewTop) {
      wrap.scrollTop = Math.max(0, nodeTop - 12);
    }
  }

  goToPage(pageNumber: number): void {
    if (pageNumber < 1) {
      return;
    }
    void this.router.navigate(['/documents', this.documentId, 'pages', pageNumber]);
  }
}
