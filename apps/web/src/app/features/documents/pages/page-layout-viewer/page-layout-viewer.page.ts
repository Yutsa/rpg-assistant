import { Component, computed, inject, signal } from '@angular/core';
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

  readonly documentId = this.route.snapshot.paramMap.get('documentId') ?? '';
  readonly pageNumber = signal(1);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly pageMeta = signal<PageMeta | null>(null);
  readonly nodes = signal<PageNode[]>([]);
  readonly renderUrl = signal('');
  readonly imageWidth = signal(0);
  readonly imageHeight = signal(0);
  readonly hoveredNodeId = signal<string | null>(null);
  readonly selectedNode = signal<PageNode | null>(null);

  readonly showBlocks = signal(true);
  readonly showLines = signal(false);
  readonly showSpans = signal(false);

  readonly overlayNodes = computed(() => {
    const meta = this.pageMeta();
    const imgW = this.imageWidth();
    const imgH = this.imageHeight();
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
          this.hoveredNodeId.set(null);
        }),
        switchMap((pageNumber) =>
          combineLatest([
            this.api.getPageMeta(this.documentId, pageNumber),
            this.api.listPageNodes(this.documentId, pageNumber),
          ]).pipe(
            map(([meta, nodes]) => ({
              meta,
              nodes,
              renderUrl: this.api.getPageRenderUrl(this.documentId, pageNumber),
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
      });
  }

  onImageLoad(event: Event): void {
    const image = event.target as HTMLImageElement;
    this.imageWidth.set(image.naturalWidth);
    this.imageHeight.set(image.naturalHeight);
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
  }

  goToPage(pageNumber: number): void {
    if (pageNumber < 1) {
      return;
    }
    void this.router.navigate(['/documents', this.documentId, 'pages', pageNumber]);
  }
}
