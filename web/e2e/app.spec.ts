import { expect, test } from "@playwright/test";

test.describe("RPG Assistant UI", () => {
  test("affiche la liste des campagnes", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Campagnes" })).toBeVisible();
    await expect(page.getByRole("link", { name: /Momie/i })).toBeVisible();
    await expect(page.getByText("1 document(s)")).toBeVisible();
  });

  test("navigue vers les documents d'une campagne", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /Momie/i }).click();
    await expect(page.getByRole("heading", { name: /Documents — momie/i })).toBeVisible();
    await expect(page.getByRole("link", { name: "test.pdf" })).toBeVisible();
    await expect(page.locator("main").getByText(/sections · .* chunks · .* entités/)).toBeVisible();
  });

  test("explore sections et chunks d'un document", async ({ page }) => {
    await page.goto("/documents/doc_test");
    await expect(page.getByRole("heading", { name: "Sections" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Intro/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Hello adventurer/ })).toBeVisible();
    await page.getByRole("link", { name: /Hello adventurer/ }).click();
    await expect(page).toHaveURL(/\/chunks\/chunk_1$/);
    await expect(page.getByText("Hello adventurer", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Voir la source" })).toBeVisible();
  });

  test("ouvre le panneau PDF depuis un chunk", async ({ page }) => {
    await page.goto("/documents/doc_test/chunks/chunk_1");
    await page.getByRole("button", { name: "Voir la source" }).click();
    await expect(page.getByText("Source PDF — page 1")).toBeVisible();
  });

  test("liste et filtre les fiches COF2", async ({ page }) => {
    await page.goto("/documents/doc_test/stat-blocks");
    await expect(page.getByRole("heading", { name: "Fiches COF2" })).toBeVisible();
    await expect(page.getByRole("link", { name: /Gobelin/ })).toBeVisible();
    await page.getByPlaceholder("Filtrer par nom…").fill("zzz");
    await expect(page.getByText("Aucune fiche stat pour ce document.")).toBeVisible();
    await page.getByPlaceholder("Filtrer par nom…").fill("gob");
    await expect(page.getByRole("link", { name: /Gobelin/ })).toBeVisible();
  });

  test("affiche le detail d'une fiche stat", async ({ page }) => {
    await page.goto("/documents/doc_test/stat-blocks/Gobelin");
    await expect(page.getByRole("heading", { name: "Gobelin", exact: true })).toBeVisible();
    await expect(page.getByText("NC 1")).toBeVisible();
    await expect(page.getByRole("rowheader", { name: "FOR" })).toBeVisible();
    await expect(page.getByText("Coup sournois")).toBeVisible();
    await page.getByRole("button", { name: "Voir la source" }).click();
    await expect(page.getByText("Source PDF — page 1")).toBeVisible();
  });

  test("fil d'Ariane et sous-navigation document", async ({ page }) => {
    await page.goto("/documents/doc_test");
    await expect(page.getByRole("navigation", { name: "Fil d'Ariane" })).toContainText("doc_test");
    const exploration = page.locator("nav.sub-nav").getByRole("link", { name: "Exploration" });
    await expect(exploration).toHaveClass(/active/);
    await page.locator("nav.sub-nav").getByRole("link", { name: "Fiches stats" }).click();
    await expect(page).toHaveURL(/\/stat-blocks$/);
    await expect(page.locator("nav.sub-nav").getByRole("link", { name: "Fiches stats" })).toHaveClass(/active/);
  });

  test("lien vers fiche depuis chunk stat_block", async ({ page }) => {
    await page.goto("/documents/doc_test/chunks/chunk_stat");
    await expect(page.getByRole("link", { name: /Fiche Gobelin/ })).toBeVisible();
    await page.getByRole("link", { name: /Fiche Gobelin/ }).click();
    await expect(page).toHaveURL(/\/stat-blocks\/Gobelin$/);
    await expect(page.getByRole("heading", { name: "Gobelin", exact: true })).toBeVisible();
  });
});
