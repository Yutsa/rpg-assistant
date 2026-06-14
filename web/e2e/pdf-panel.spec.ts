import { expect, test } from "@playwright/test";

import { openDocument } from "./helpers";

test.describe("Panneau PDF source", () => {
  test.beforeEach(async ({ page }) => {
    await openDocument(page);
    await page.getByRole("link", { name: /Hello adventurer/ }).click();
  });

  test("affiche le rendu PDF avec surlignage bbox", async ({ page }) => {
    await page.getByRole("button", { name: "Voir la source" }).click();

    await expect(page.getByText("Source PDF — page 1")).toBeVisible();
    const pdfImage = page.getByRole("img", { name: "Page 1" });
    await expect(pdfImage).toBeVisible({ timeout: 20_000 });
    await expect(page.locator(".pdf-overlay .source-highlight").first()).toBeVisible();
  });

  test("affiche le panneau PDF depuis une fiche stat", async ({ page }) => {
    await page.goto("/documents/doc_e2e/stat-blocks/Orc");
    await expect(page.getByRole("heading", { name: "Orc", level: 2 })).toBeVisible();

    await page.getByRole("button", { name: "Voir la source" }).click();
    await expect(page.getByText("Source PDF — page 1")).toBeVisible();
    await expect(page.getByRole("img", { name: "Page 1" })).toBeVisible({ timeout: 20_000 });
  });
});

test.describe("PDF introuvable — override de chemin", () => {
  test("permet de saisir un chemin absolu quand le rendu PDF échoue", async ({ page }) => {
    await page.route("**/api/documents/doc_e2e/pages/1/render**", (route) => {
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ error: "PDF not found", code: "pdf_not_found" }),
      });
    });

    await openDocument(page);
    await page.getByRole("link", { name: /Hello adventurer/ }).click();
    await page.getByRole("button", { name: "Voir la source" }).click();

    await expect(page.getByPlaceholder("/chemin/vers/aventure.pdf")).toBeVisible({
      timeout: 20_000,
    });
    await page.getByPlaceholder("/chemin/vers/aventure.pdf").fill("/tmp/fake.pdf");
    await page.getByRole("button", { name: "Enregistrer le chemin" }).click();

    const stored = await page.evaluate(() =>
      localStorage.getItem("rpg-assistant:pdf-path:doc_e2e"),
    );
    expect(stored).toBe("/tmp/fake.pdf");
  });
});
