import { expect, test } from "@playwright/test";

import { openCampaign, openDocument } from "./helpers";

test.describe("Fiches COF2", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/documents/doc_e2e/stat-blocks");
    await expect(page.getByRole("heading", { name: "Fiches COF2", level: 2 })).toBeVisible();
  });

  test("liste les fiches avec nom, NC et pages", async ({ page }) => {
    await expect(page.getByRole("link", { name: /Gobelin NC 1/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Gobelin NC 2/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Orc NC 3/ })).toBeVisible();
  });

  test("filtre les fiches par nom", async ({ page }) => {
    await page.getByPlaceholder("Filtrer par nom…").fill("orc");
    await expect(page.getByRole("link", { name: /Orc NC 3/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Gobelin NC 1/ })).toHaveCount(0);

    await page.getByPlaceholder("Filtrer par nom…").fill("zzz");
    await expect(page.getByText("Aucune fiche stat pour ce document.")).toBeVisible();
  });

  test("affiche le détail d'une fiche avec attributs et capacités", async ({ page }) => {
    await page.getByRole("link", { name: /Orc NC 3/ }).click();

    await expect(page).toHaveURL(/\/stat-blocks\/Orc/);
    await expect(page.getByRole("heading", { name: "Orc", level: 2 })).toBeVisible();
    await expect(page.getByText("NC 3")).toBeVisible();
    await expect(page.locator("th", { hasText: "FOR" })).toBeVisible();
    await expect(page.locator("td", { hasText: "16" })).toBeVisible();
    await expect(page.getByText("Furie")).toBeVisible();
    await expect(page.getByRole("button", { name: "Voir la source" })).toBeVisible();
  });

  test("gère l'ambiguïté quand plusieurs fiches portent le même nom", async ({ page }) => {
    await page.goto("/documents/doc_e2e/stat-blocks/Gobelin");

    await expect(page.getByText("Plusieurs fiches correspondent à ce nom.")).toBeVisible();
    await expect(page.getByRole("link", { name: /Gobelin \(NC 1/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Gobelin \(NC 2/ })).toBeVisible();
  });

  test("accède aux fiches depuis l'explorateur via la sous-navigation", async ({ page }) => {
    await openDocument(page);
    await page.getByRole("link", { name: "Fiches stats" }).click();
    await expect(page.getByRole("heading", { name: "Fiches COF2", level: 2 })).toBeVisible();
    await expect(page.getByRole("link", { name: /Gobelin NC 1/ })).toBeVisible();
  });
});
