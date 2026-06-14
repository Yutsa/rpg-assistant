import { expect, test } from "@playwright/test";

import { openDocument } from "./helpers";

test.describe("Explorateur de document", () => {
  test.beforeEach(async ({ page }) => {
    await openDocument(page);
  });

  test("affiche l'arborescence des sections et sélectionne une section", async ({ page }) => {
    const sectionNav = page.getByRole("navigation", { name: "Sections" });
    await expect(sectionNav.getByRole("button", { name: /Introduction/ })).toBeVisible();
    await expect(sectionNav.getByRole("button", { name: /Scène d'ouverture/ })).toBeVisible();

    await page.goto("/documents/doc_e2e?section=sec_intro");
    await expect(page.locator(".chunk-list .chunk-item")).toHaveCount(1);
    await expect(page.getByText("Orc NC 3")).toBeVisible();

    await page.goto("/documents/doc_e2e?section=sec_scene");
    await expect(page.locator(".chunk-list .chunk-item")).toHaveCount(3);
  });

  test("affiche la liste des chunks avec aperçu et badges", async ({ page }) => {
    const narrativeLink = page.getByRole("link", { name: /Hello adventurer/ });
    await expect(narrativeLink).toBeVisible();
    await expect(narrativeLink).toContainText("p.1");
    await expect(narrativeLink).toContainText("narrative");

    const statLink = page.getByRole("link", { name: /Gobelin NC 1/ });
    await expect(statLink).toBeVisible();
    await expect(statLink).toContainText("stat_block");
  });

  test("ouvre le détail d'un chunk avec texte et métadonnées", async ({ page }) => {
    await page.getByRole("link", { name: /Hello adventurer/ }).click();

    await expect(page).toHaveURL(/\/chunks\/chunk_narrative/);
    await expect(page.getByRole("heading", { name: "Chunk", level: 2 })).toBeVisible();
    await expect(page.getByText("Hello adventurer — vous entrez dans la crypte.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Voir la source" })).toBeVisible();

    await page.getByText("Métadonnées").click();
    await expect(page.getByText(/"source_spans"/)).toBeVisible();
    await expect(page.getByText(/blk_narrative/)).toBeVisible();
  });

  test("propose le lien vers la fiche stat depuis un chunk stat_block", async ({ page }) => {
    await page.getByRole("link", { name: /Gobelin NC 1/ }).click();

    await expect(page.getByRole("link", { name: "Fiche Gobelin" })).toBeVisible();
    await page.getByRole("link", { name: "Fiche Gobelin" }).click();

    await expect(page).toHaveURL(/\/stat-blocks\/Gobelin/);
    await expect(page.getByText("Plusieurs fiches correspondent à ce nom.")).toBeVisible();
  });

  test("bascule entre Exploration et Fiches stats via la sous-navigation", async ({ page }) => {
    await page.getByRole("link", { name: "Fiches stats" }).click();
    await expect(page).toHaveURL(/\/stat-blocks$/);
    await expect(page.getByRole("heading", { name: "Fiches COF2", level: 2 })).toBeVisible();

    await page.getByRole("link", { name: "Exploration" }).click();
    await expect(page).toHaveURL(/\/documents\/doc_e2e/);
    await expect(page.getByRole("navigation", { name: "Sections" })).toBeVisible();
  });
});
