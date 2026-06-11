import { useMemo, useState } from "react";

import type { PageBlock, PdfHighlight } from "../../api/types";
import { bboxToViewport } from "../../utils/bbox";

interface OverlayRect {
  key: string;
  rect: ReturnType<typeof bboxToViewport>;
  highlighted: boolean;
  label?: string;
}

function rectsFromHighlight(
  blocks: PageBlock[],
  highlight: PdfHighlight | null,
  pageWidthPts: number,
  imageWidthPx: number,
): OverlayRect[] {
  const highlightIds = new Set(highlight?.pageBlockIds ?? []);
  const rects: OverlayRect[] = [];

  for (const block of blocks) {
    const highlighted = highlightIds.has(block.id);
    rects.push({
      key: block.id,
      rect: bboxToViewport(block.bbox, pageWidthPts, imageWidthPx),
      highlighted,
      label: block.text.slice(0, 80),
    });
  }

  if (highlight?.bboxFallbacks?.length) {
    highlight.bboxFallbacks.forEach((bbox, index) => {
      rects.push({
        key: `fallback-${index}`,
        rect: bboxToViewport(bbox, pageWidthPts, imageWidthPx),
        highlighted: true,
      });
    });
  }

  return rects;
}

export function BboxOverlay({
  blocks,
  highlight,
  pageWidthPts,
  imageWidthPx,
  imageHeightPx,
}: {
  blocks: PageBlock[];
  highlight: PdfHighlight | null;
  pageWidthPts: number;
  imageWidthPx: number;
  imageHeightPx: number;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const rects = useMemo(
    () => rectsFromHighlight(blocks, highlight, pageWidthPts, imageWidthPx),
    [blocks, highlight, pageWidthPts, imageWidthPx],
  );

  return (
    <svg
      className="pdf-overlay"
      width={imageWidthPx}
      height={imageHeightPx}
      aria-hidden
    >
      {rects.map((item) => (
        <rect
          key={item.key}
          className={item.label ? "hoverable" : undefined}
          x={item.rect.left}
          y={item.rect.top}
          width={item.rect.width}
          height={item.rect.height}
          fill={item.highlighted ? "var(--highlight)" : "transparent"}
          stroke={item.highlighted ? "#c98d1a" : "transparent"}
          strokeWidth={1}
          onMouseEnter={() => item.label && setHovered(item.key)}
          onMouseLeave={() => setHovered(null)}
        >
          {hovered === item.key && item.label && <title>{item.label}</title>}
        </rect>
      ))}
    </svg>
  );
}
