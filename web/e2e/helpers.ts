import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

export async function waitForAppReady(page: Page) {
  await expect(page.getByRole("heading", { name: "RPG Assistant", level: 1 })).toBeVisible();
}

export async function openCampaign(page: Page, campaignTitle = "Momie") {
  await page.goto("/");
  await waitForAppReady(page);
  await expect(page.getByRole("heading", { name: "Campagnes", level: 2 })).toBeVisible();
  await page.getByRole("link", { name: new RegExp(campaignTitle) }).click();
  await expect(page.getByRole("heading", { name: /Documents — momie/i })).toBeVisible();
}

export async function openDocument(page: Page, filename = "aventure-test.pdf") {
  await openCampaign(page);
  await page.getByRole("link", { name: filename }).click();
  await expect(page.getByRole("navigation", { name: "Sections" })).toBeVisible();
  await selectSceneSection(page);
}

export async function selectSceneSection(page: Page) {
  await page.goto("/documents/doc_e2e?section=sec_scene");
  await expect(page.getByRole("navigation", { name: "Sections" })).toBeVisible();
  await waitForChunksLoaded(page);
}

export async function waitForChunksLoaded(page: Page) {
  await expect(page.locator(".chunk-list .chunk-item").first()).toBeVisible({
    timeout: 15_000,
  });
}
