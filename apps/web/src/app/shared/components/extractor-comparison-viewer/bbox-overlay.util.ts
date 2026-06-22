import { PageBlock } from '../../../core/models/campaign.models';

export type CompareLane = 'pymupdf' | 'pdfbox';

export interface OverlayBlock extends PageBlock {
  screenX: number;
  screenY: number;
  screenWidth: number;
  screenHeight: number;
}

export interface BlockSelection {
  lane: CompareLane;
  block: PageBlock;
}

interface Bbox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

const MIN_MATCH_IOU = 0.05;

export function mapBlocksToOverlay(
  blocks: PageBlock[],
  pageWidth: number,
  pageHeight: number,
  displayWidth: number,
  displayHeight: number,
): OverlayBlock[] {
  if (!pageWidth || !pageHeight || !displayWidth || !displayHeight) {
    return [];
  }
  const scaleX = displayWidth / pageWidth;
  const scaleY = displayHeight / pageHeight;
  return blocks.map((block) => ({
    ...block,
    screenX: block.bbox.x0 * scaleX,
    screenY: block.bbox.y0 * scaleY,
    screenWidth: (block.bbox.x1 - block.bbox.x0) * scaleX,
    screenHeight: (block.bbox.y1 - block.bbox.y0) * scaleY,
  }));
}

function bboxArea(bbox: Bbox): number {
  return Math.max(0, bbox.x1 - bbox.x0) * Math.max(0, bbox.y1 - bbox.y0);
}

function bboxIntersection(a: Bbox, b: Bbox): number {
  const x0 = Math.max(a.x0, b.x0);
  const y0 = Math.max(a.y0, b.y0);
  const x1 = Math.min(a.x1, b.x1);
  const y1 = Math.min(a.y1, b.y1);
  return Math.max(0, x1 - x0) * Math.max(0, y1 - y0);
}

export function bboxIoU(a: Bbox, b: Bbox): number {
  const intersection = bboxIntersection(a, b);
  if (intersection === 0) {
    return 0;
  }
  const union = bboxArea(a) + bboxArea(b) - intersection;
  return union > 0 ? intersection / union : 0;
}

function bboxCenterDistance(a: Bbox, b: Bbox): number {
  const ax = (a.x0 + a.x1) / 2;
  const ay = (a.y0 + a.y1) / 2;
  const bx = (b.x0 + b.x1) / 2;
  const by = (b.y0 + b.y1) / 2;
  return Math.hypot(ax - bx, ay - by);
}

export function findBestMatchBlock(
  source: PageBlock,
  candidates: PageBlock[],
): PageBlock | null {
  if (candidates.length === 0) {
    return null;
  }

  let bestIoU = -1;
  let bestByIoU: PageBlock | null = null;
  for (const candidate of candidates) {
    const iou = bboxIoU(source.bbox, candidate.bbox);
    if (iou > bestIoU) {
      bestIoU = iou;
      bestByIoU = candidate;
    }
  }

  if (bestByIoU && bestIoU >= MIN_MATCH_IOU) {
    return bestByIoU;
  }

  let bestDistance = Number.POSITIVE_INFINITY;
  let bestByDistance: PageBlock | null = null;
  for (const candidate of candidates) {
    const distance = bboxCenterDistance(source.bbox, candidate.bbox);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestByDistance = candidate;
    }
  }

  return bestByDistance;
}
