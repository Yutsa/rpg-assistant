import { describe, expect, it } from "vitest";

import { bboxToViewport } from "./bbox";

describe("bboxToViewport", () => {
  it("scales PDF points to rendered image pixels", () => {
    const rect = bboxToViewport(
      { x0: 10, y0: 20, x1: 110, y1: 60 },
      595,
      1190,
    );
    expect(rect.left).toBeCloseTo(20);
    expect(rect.top).toBeCloseTo(40);
    expect(rect.width).toBeCloseTo(200);
    expect(rect.height).toBeCloseTo(80);
  });
});
