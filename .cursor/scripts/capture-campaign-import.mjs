#!/usr/bin/env node
/**
 * Preuve visuelle : dialog d'import + page document post-import.
 *
 * Usage:
 *   node .cursor/scripts/capture-campaign-import.mjs [PDF_PATH] [CAMPAIGN_ID]
 *
 * Prérequis: stack dev démarrée (dev-stack.sh restart).
 */
import { mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.join(scriptDir, '../../apps/web');
const require = createRequire(path.join(webRoot, 'package.json'));
const { chromium } = require('@playwright/test');

const rootDir = path.resolve(scriptDir, '../..');
const pdfPath = path.resolve(
  process.argv[2] ?? path.join(rootDir, 'data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf'),
);
const campaignId = process.argv[3] ?? `import-demo-${Date.now().toString(36)}`;
const artifactsDir = process.env.CURSOR_ARTIFACTS_DIR ?? '/opt/cursor/artifacts';
const dialogShot = path.join(artifactsDir, 'verification-import-dialog.png');
const documentShot = path.join(artifactsDir, 'verification-import-document.png');

const baseURL = process.env.WEB_BASE_URL ?? 'http://127.0.0.1:4200';

await mkdir(artifactsDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

try {
  await page.goto(`${baseURL}/campaigns`, { waitUntil: 'networkidle' });
  await page.getByTestId('open-import-dialog').click();
  await page.getByTestId('import-campaign-dialog').waitFor({ state: 'visible' });

  await page.getByTestId('import-file-input').setInputFiles(pdfPath);
  await page.getByTestId('import-campaign-id').fill(campaignId);
  await page.getByTestId('import-campaign-title').fill('Import démo UI');
  await page.getByTestId('import-game-system').click();
  await page.getByRole('option', { name: /Chroniques Oubliées Fantasy 2/i }).click();

  await page.getByTestId('import-campaign-dialog').screenshot({ path: dialogShot });
  console.log('Dialog screenshot:', dialogShot);

  await page.getByTestId('import-submit').click();
  await page.getByTestId('import-progress').waitFor({ state: 'visible', timeout: 30_000 });
  await page.waitForURL(/\/documents\/doc_/, { timeout: 300_000 });
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: documentShot, fullPage: false });
  console.log('Document screenshot:', documentShot);
  console.log('Campaign ID:', campaignId);
  console.log('Document URL:', page.url());
} finally {
  await browser.close();
}
