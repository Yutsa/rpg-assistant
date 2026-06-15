import { expect, test } from '@playwright/test';

import { E2E } from '../fixtures/e2e-data';
import { DocumentExplorerPage } from '../pages/document-explorer.page';

test.describe('Document sections integration', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      document.body.classList.add('e2e-no-animations');
    });
  });

  test('renders hierarchical section tree from API', async ({ page }) => {
    const explorer = new DocumentExplorerPage(page);
    await explorer.goto(E2E.documentId);

    await expect(explorer.section(E2E.sections.intro)).toBeVisible();
    await expect(explorer.section(E2E.sections.ch1)).toBeVisible();
    await expect(explorer.section(E2E.sections.annex)).toBeVisible();
    await expect(explorer.section(E2E.sections.intro)).toContainText('Introduction');
    await expect(explorer.section(E2E.sections.ch1)).toContainText('Chapitre 1');
  });
});
