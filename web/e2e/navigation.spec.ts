import { expect, test } from "@playwright/test";

import { openCampaign, openDocument, waitForAppReady } from "./helpers";

test.describe("Navigation et fil d'Ariane", () => {
  test("retrouve la page d'accueil via le fil d'Ariane", async ({ page }) => {
    await openDocument(page);
    await page.getByRole("link", { name: "Campagnes" }).click();

    await expect(page).toHaveURL("/");
    await expect(page.getByRole("heading", { name: "Campagnes", level: 2 })).toBeVisible();
  });

  test("affiche le fil d'Ariane sur la page campagne", async ({ page }) => {
    await openCampaign(page);

    const breadcrumb = page.getByRole("navigation", { name: "Fil d'Ariane" });
    await expect(breadcrumb.getByRole("link", { name: "Campagnes" })).toBeVisible();
    await expect(breadcrumb.getByText("momie")).toBeVisible();
  });

  test("affiche le fil d'Ariane sur une fiche stat", async ({ page }) => {
    await page.goto("/documents/doc_e2e/stat-blocks/Orc");
    await waitForAppReady(page);

    const breadcrumb = page.getByRole("navigation", { name: "Fil d'Ariane" });
    await expect(breadcrumb.getByRole("link", { name: "Campagnes" })).toBeVisible();
    await expect(breadcrumb.getByRole("link", { name: "doc_e2e" })).toBeVisible();
    await expect(breadcrumb.getByRole("link", { name: "Fiches stats" })).toBeVisible();
    await expect(breadcrumb.getByText("Orc")).toBeVisible();
  });

  test("redirige les routes inconnues vers l'accueil", async ({ page }) => {
    await page.goto("/route-inexistante");
    await waitForAppReady(page);
    await expect(page).toHaveURL("/");
    await expect(page.getByRole("heading", { name: "Campagnes", level: 2 })).toBeVisible();
  });

  test("affiche le fil d'Ariane chunk dans l'explorateur", async ({ page }) => {
    await openDocument(page);
    await page.getByRole("link", { name: /Hello adventurer/ }).click();

    const breadcrumb = page.getByRole("navigation", { name: "Fil d'Ariane" });
    await expect(breadcrumb.getByText("chunk_narrative")).toBeVisible();
  });
});
