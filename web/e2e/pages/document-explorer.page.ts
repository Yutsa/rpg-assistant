import { expect, type Locator, type Page } from '@playwright/test';

export class DocumentExplorerPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async goto(documentId: string): Promise<void> {
    await this.page.goto(`/documents/${documentId}`);
    await expect(this.page.getByTestId('document-explorer-page')).toBeVisible();
  }

  async gotoChunk(documentId: string, chunkId: string): Promise<void> {
    await this.page.goto(`/documents/${documentId}/chunks/${chunkId}`);
    await expect(this.page.getByTestId('document-explorer-page')).toBeVisible();
  }

  async gotoStatBlock(documentId: string, name: string): Promise<void> {
    await this.page.goto(`/documents/${documentId}/stat-blocks/${encodeURIComponent(name)}`);
    await expect(this.page.getByTestId('document-explorer-page')).toBeVisible();
  }

  section(sectionId: string): Locator {
    return this.page.getByTestId(`section-${sectionId}`);
  }

  chunkItem(chunkId: string): Locator {
    return this.page.getByTestId(`chunk-item-${chunkId}`);
  }

  statBlockItem(name: string): Locator {
    return this.page.getByTestId(`stat-block-item-${name}`);
  }

  async openChunksTab(): Promise<void> {
    await this.page.getByRole('tab', { name: 'Chunks' }).click();
  }

  async openStatBlocksTab(): Promise<void> {
    await this.page.getByRole('tab', { name: 'Stat blocks' }).click();
  }
}
