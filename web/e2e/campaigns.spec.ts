import { expect, test } from "@playwright/test";

import { openCampaign, openDocument, waitForAppReady } from "./helpers";

test.describe("Liste des campagnes", () => {
  test("affiche les campagnes importées avec métadonnées", async ({ page }) => {
    await page.goto("/");
    await waitForAppReady(page);

    await expect(page.getByRole("heading", { name: "Campagnes", level: 2 })).toBeVisible();
    const momieCard = page.getByRole("link", { name: /Momie/ });
    await expect(momieCard).toBeVisible();
    await expect(momieCard).toContainText("1 document(s)");
    await expect(momieCard).toContainText("cof2");
  });

  test("navigue vers les documents d'une campagne", async ({ page }) => {
    await openCampaign(page);

    await expect(page.getByText(/2 sections · 4 chunks · 1 entités/)).toBeVisible();
    const docLink = page.getByRole("link", { name: "aventure-test.pdf" });
    await expect(docLink).toBeVisible();
    await expect(docLink).toContainText("1 pages");
    await expect(docLink).toContainText("Import raw : completed");
  });

  test("affiche l'état vide pour une campagne sans document", async ({ page }) => {
    await page.goto("/campaigns/vide");
    await waitForAppReady(page);

    await expect(page.getByRole("heading", { name: /Aucun document pour vide/i })).toBeVisible();
  });
});

test.describe("Sélecteur de documents", () => {
  test("ouvre l'explorateur depuis la carte document", async ({ page }) => {
    await openDocument(page);

    await expect(page.getByRole("link", { name: "Exploration" })).toHaveClass(/active/);
    await expect(page.getByRole("link", { name: "Fiches stats" })).toBeVisible();
  });
});
