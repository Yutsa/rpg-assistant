import { expect, test } from '@playwright/test';

import { E2E } from '../fixtures/e2e-data';
import { DocumentExplorerPage } from '../pages/document-explorer.page';

test.describe('Chunks integration', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      document.body.classList.add('e2e-no-animations');
    });
  });

  test('filters chunks when a section is selected', async ({ page }) => {
    const explorer = new DocumentExplorerPage(page);
    await explorer.goto(E2E.documentId);
    await explorer.openChunksTab();

    await expect(explorer.chunkItem(E2E.chunks.intro)).toBeVisible();
    await expect(explorer.chunkItem(E2E.chunks.ch1)).toBeVisible();

    await explorer.section(E2E.sections.ch1).click();

    await expect(explorer.chunkItem(E2E.chunks.ch1)).toBeVisible();
    await expect(explorer.chunkItem(E2E.chunks.ch1b)).toBeVisible();
    await expect(explorer.chunkItem(E2E.chunks.intro)).toHaveCount(0);
  });

  test('shows chunk detail from direct URL', async ({ page }) => {
    const explorer = new DocumentExplorerPage(page);
    await explorer.gotoChunk(E2E.documentId, E2E.chunks.intro);

    await expect(page.getByTestId('chunk-viewer')).toBeVisible();
    await expect(page.getByTestId('chunk-text')).toContainText("Bienvenue dans l'aventure E2E");
  });
});
