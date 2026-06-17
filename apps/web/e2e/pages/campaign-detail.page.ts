import { expect, type Locator, type Page } from '@playwright/test';

export class CampaignDetailPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async goto(campaignId: string): Promise<void> {
    await this.page.goto(`/campaigns/${campaignId}`);
    await expect(this.page.getByTestId('campaign-detail-page')).toBeVisible();
  }

  documentCard(documentId: string): Locator {
    return this.page.getByTestId(`document-card-${documentId}`);
  }
}
