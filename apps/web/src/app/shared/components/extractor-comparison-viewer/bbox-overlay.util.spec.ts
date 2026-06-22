import { PageBlock } from '../../../core/models/campaign.models';
import { bboxIoU, findBestMatchBlock } from './bbox-overlay.util';

function block(id: string, bbox: PageBlock['bbox']): PageBlock {
  return {
    id,
    page_number: 1,
    block_index: 0,
    text: id,
    bbox,
    metadata: {},
  };
}

describe('bboxIoU', () => {
  it('returns 1 for identical boxes', () => {
    const bbox = { x0: 0, y0: 0, x1: 10, y1: 10 };
    expect(bboxIoU(bbox, bbox)).toBe(1);
  });

  it('returns 0 for disjoint boxes', () => {
    const a = { x0: 0, y0: 0, x1: 10, y1: 10 };
    const b = { x0: 20, y0: 20, x1: 30, y1: 30 };
    expect(bboxIoU(a, b)).toBe(0);
  });

  it('returns partial overlap ratio', () => {
    const a = { x0: 0, y0: 0, x1: 10, y1: 10 };
    const b = { x0: 5, y0: 0, x1: 15, y1: 10 };
    expect(bboxIoU(a, b)).toBeCloseTo(50 / 150, 5);
  });
});

describe('findBestMatchBlock', () => {
  it('prefers overlapping candidate over distant one', () => {
    const source = block('src', { x0: 0, y0: 0, x1: 10, y1: 10 });
    const overlap = block('overlap', { x0: 8, y0: 0, x1: 18, y1: 10 });
    const distant = block('distant', { x0: 100, y0: 100, x1: 110, y1: 110 });

    expect(findBestMatchBlock(source, [distant, overlap])?.id).toBe('overlap');
  });

  it('falls back to nearest center when no overlap', () => {
    const source = block('src', { x0: 0, y0: 0, x1: 10, y1: 10 });
    const near = block('near', { x0: 20, y0: 0, x1: 30, y1: 10 });
    const far = block('far', { x0: 200, y0: 200, x1: 210, y1: 210 });

    expect(findBestMatchBlock(source, [far, near])?.id).toBe('near');
  });

  it('returns null for empty candidates', () => {
    const source = block('src', { x0: 0, y0: 0, x1: 10, y1: 10 });
    expect(findBestMatchBlock(source, [])).toBeNull();
  });
});
