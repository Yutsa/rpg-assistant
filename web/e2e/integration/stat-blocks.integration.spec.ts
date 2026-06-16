import { expect, test } from '@playwright/test';

import { E2E } from '../fixtures/e2e-data';
import { DocumentExplorerPage } from '../pages/document-explorer.page';

test.describe('Stat blocks integration', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      document.body.classList.add('e2e-no-animations');
    });
  });

  test('lists stat blocks and opens detail', async ({ page }) => {
    const explorer = new DocumentExplorerPage(page);
    await explorer.goto(E2E.documentId);
    await explorer.openStatBlocksTab();

    await expect(explorer.statBlockItem(E2E.statBlocks.gobelin)).toBeVisible();
    await expect(explorer.statBlockItem(E2E.statBlocks.orc)).toBeVisible();

    await explorer.statBlockItem(E2E.statBlocks.gobelin).click();

    await expect(page.getByTestId('stat-block-viewer')).toBeVisible();
    await expect(page.getByTestId('stat-block-name')).toHaveText(E2E.statBlocks.gobelin);
    await expect(page.getByTestId('stat-block-nc')).toHaveText('NC 1');
    await expect(page.getByTestId('stat-block-attributes')).toContainText('FOR');
  });
});
