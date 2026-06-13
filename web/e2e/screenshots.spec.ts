import { expect, test, type Page } from "@playwright/test";

const VIEWPORT = { width: 1280, height: 800 };

async function ready(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".app-shell")).toBeVisible();
}

async function shot(page: Page, name: string) {
  await expect(page.locator(".app-shell")).toHaveScreenshot(`${name}.png`, {
    animations: "disabled",
  });
}

test.describe("RPG Assistant UI — screenshots", () => {
  test.use({ viewport: VIEWPORT });

  test("liste des campagnes", async ({ page }) => {
    await page.goto("/");
    await ready(page);
    await shot(page, "campaign-list");
  });

  test("documents d'une campagne", async ({ page }) => {
    await page.goto("/campaigns/momie");
    await ready(page);
    await shot(page, "document-picker");
  });

  test("explorateur document", async ({ page }) => {
    await page.goto("/documents/doc_test");
    await ready(page);
    await shot(page, "document-explorer");
  });

  test("lecteur de chunk", async ({ page }) => {
    await page.goto("/documents/doc_test/chunks/chunk_1");
    await ready(page);
    await shot(page, "chunk-reader");
  });

  test("chunk stat_block avec lien fiche", async ({ page }) => {
    await page.goto("/documents/doc_test/chunks/chunk_stat");
    await ready(page);
    await shot(page, "chunk-stat-block");
  });

  test("panneau PDF depuis un chunk", async ({ page }) => {
    await page.goto("/documents/doc_test/chunks/chunk_1");
    await ready(page);
    await page.getByRole("button", { name: "Voir la source" }).click();
    await expect(page.getByText("Source PDF — page 1")).toBeVisible();
    await shot(page, "chunk-pdf-panel");
  });

  test("liste des fiches COF2", async ({ page }) => {
    await page.goto("/documents/doc_test/stat-blocks");
    await ready(page);
    await shot(page, "stat-blocks-list");
  });

  test("detail fiche COF2", async ({ page }) => {
    await page.goto("/documents/doc_test/stat-blocks/Gobelin");
    await ready(page);
    await shot(page, "stat-block-detail");
  });

  test("detail fiche COF2 avec panneau PDF", async ({ page }) => {
    await page.goto("/documents/doc_test/stat-blocks/Gobelin");
    await ready(page);
    await page.getByRole("button", { name: "Voir la source" }).click();
    await expect(page.getByText("Source PDF — page 1")).toBeVisible();
    await shot(page, "stat-block-detail-pdf-panel");
  });
});
