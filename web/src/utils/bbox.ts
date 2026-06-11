import type { BBox } from "../api/types";

export interface ViewportRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export function bboxToViewport(
  bbox: BBox,
  pageWidthPts: number,
  imageWidthPx: number,
): ViewportRect {
  const scale = imageWidthPx / pageWidthPts;
  return {
    left: bbox.x0 * scale,
    top: bbox.y0 * scale,
    width: (bbox.x1 - bbox.x0) * scale,
    height: (bbox.y1 - bbox.y0) * scale,
  };
}
