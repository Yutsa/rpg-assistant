import { expect, test } from '@playwright/test';

import { E2E } from '../fixtures/e2e-data';
import { CampaignListPage } from '../pages/campaign-list.page';

test.describe('Campaign list integration', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      document.body.classList.add('e2e-no-animations');
    });
  });

  test('displays seeded campaign from API', async ({ page }) => {
    const listPage = new CampaignListPage(page);
    await listPage.goto();

    await expect(listPage.campaignCard(E2E.campaignId)).toBeVisible();
    await expect(listPage.campaignCard(E2E.campaignId)).toContainText(E2E.campaignTitle);
  });
});
