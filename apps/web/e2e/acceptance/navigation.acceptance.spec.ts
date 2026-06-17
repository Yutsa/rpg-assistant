import { expect, test } from '@playwright/test';

import { E2E } from '../fixtures/e2e-data';
import { CampaignDetailPage } from '../pages/campaign-detail.page';
import { CampaignListPage } from '../pages/campaign-list.page';
import { DocumentExplorerPage } from '../pages/document-explorer.page';

test.describe('Campaign navigation acceptance', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      document.body.classList.add('e2e-no-animations');
    });
  });

  test('user can browse from campaigns to document explorer', async ({ page }) => {
    const listPage = new CampaignListPage(page);
    const detailPage = new CampaignDetailPage(page);
    const explorer = new DocumentExplorerPage(page);

    await listPage.goto();
    await listPage.campaignCard(E2E.campaignId).click();

    await expect(page.getByTestId('campaign-detail-page')).toBeVisible();
    await expect(detailPage.documentCard(E2E.documentId)).toBeVisible();

    await detailPage.documentCard(E2E.documentId).click();
    await expect(page.getByTestId('document-explorer-page')).toBeVisible();
    await expect(explorer.section(E2E.sections.intro)).toBeVisible();
  });
});

test.describe('Chunk exploration acceptance', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      document.body.classList.add('e2e-no-animations');
    });
  });

  test('user can open a chunk from section filter', async ({ page }) => {
    const explorer = new DocumentExplorerPage(page);
    await explorer.goto(E2E.documentId);
    await explorer.openChunksTab();
    await explorer.section(E2E.sections.ch1).click();
    await explorer.chunkItem(E2E.chunks.ch1).click();

    await expect(page.getByTestId('chunk-text')).toContainText('taverne du village');
    await expect(page.getByTestId('chunk-viewer').getByTestId('page-range-badge')).toContainText('p. 2');
  });
});

test.describe('Stat block exploration acceptance', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      document.body.classList.add('e2e-no-animations');
    });
  });

  test('user can open a stat block fiche', async ({ page }) => {
    const explorer = new DocumentExplorerPage(page);
    await explorer.goto(E2E.documentId);
    await explorer.openStatBlocksTab();
    await explorer.statBlockItem(E2E.statBlocks.orc).click();

    await expect(page.getByTestId('stat-block-name')).toHaveText(E2E.statBlocks.orc);
    await expect(page.getByTestId('stat-block-nc')).toHaveText('NC 3');
  });
});

test.describe('Error handling acceptance', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      document.body.classList.add('e2e-no-animations');
    });
  });

  test('shows friendly message for unknown document', async ({ page }) => {
    await page.goto('/documents/doc_unknown');
    await expect(page.getByTestId('document-error')).toBeVisible();
    await expect(page.getByTestId('document-error')).toContainText('introuvable');
  });
});
