import { expect, type Locator, type Page } from '@playwright/test';

export class CampaignListPage {
  readonly page: Page;
  readonly grid: Locator;

  constructor(page: Page) {
    this.page = page;
    this.grid = page.getByTestId('campaign-grid');
  }

  async goto(): Promise<void> {
    await this.page.goto('/campaigns');
    await expect(this.page.getByTestId('campaign-list-page')).toBeVisible();
  }

  campaignCard(campaignId: string): Locator {
    return this.page.getByTestId(`campaign-card-${campaignId}`);
  }
}
