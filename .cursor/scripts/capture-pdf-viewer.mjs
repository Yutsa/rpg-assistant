#!/usr/bin/env node
/**
 * Capture d'écran du visualiseur PDF (page-layout-viewer) pour preuve de vérification.
 *
 * Usage:
 *   node .cursor/scripts/capture-pdf-viewer.mjs DOCUMENT_ID PAGE OUTPUT.png
 *
 * Prérequis: stack dev démarrée (dev-stack.sh start).
 */
import { mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.join(scriptDir, '../../apps/web');
const require = createRequire(path.join(webRoot, 'package.json'));
const { chromium } = require('@playwright/test');

const [, , documentId, pageNumberRaw, outputPath] = process.argv;

if (!documentId || !pageNumberRaw || !outputPath) {
  console.error('Usage: capture-pdf-viewer.mjs DOCUMENT_ID PAGE OUTPUT.png');
  process.exit(1);
}

const pageNumber = Number.parseInt(pageNumberRaw, 10);
const baseURL = process.env.WEB_BASE_URL ?? 'http://127.0.0.1:4200';
const rootDir = path.resolve(scriptDir, '../..');
const absOutput = path.isAbsolute(outputPath)
  ? outputPath
  : path.join(rootDir, outputPath);

await mkdir(path.dirname(absOutput), { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

try {
  await page.goto(`${baseURL}/documents/${documentId}`, { waitUntil: 'networkidle' });
  await page.getByTestId('open-pdf-viewer').click();
  await page.getByTestId('detail-pdf-panel').waitFor({ state: 'visible', timeout: 30_000 });
  await page.getByTestId('page-layout-viewer').waitFor({ state: 'visible', timeout: 30_000 });

  const current = await page.getByTestId('page-layout-viewer').locator('.page-label').textContent();
  const currentNum = Number.parseInt((current ?? 'Page 1').replace(/\D+/g, ''), 10) || 1;
  const delta = pageNumber - currentNum;
  const nav =
    delta > 0
      ? page.getByLabel('Page suivante')
      : delta < 0
        ? page.getByLabel('Page précédente')
        : null;

  if (nav) {
    for (let i = 0; i < Math.abs(delta); i += 1) {
      await nav.click();
    }
  }

  await page.getByTestId('page-layout-viewer').locator('.page-label').filter({ hasText: `Page ${pageNumber}` }).waitFor({
    timeout: 15_000,
  });

  await page.waitForTimeout(1500);
  await page.getByTestId('detail-pdf-panel').screenshot({ path: absOutput });
  console.log(absOutput);
} finally {
  await browser.close();
}
