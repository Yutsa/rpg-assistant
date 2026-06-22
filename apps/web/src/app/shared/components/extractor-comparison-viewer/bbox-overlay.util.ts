import { PageBlock } from '../../../core/models/campaign.models';

export interface OverlayBlock extends PageBlock {
  screenX: number;
  screenY: number;
  screenWidth: number;
  screenHeight: number;
}

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
