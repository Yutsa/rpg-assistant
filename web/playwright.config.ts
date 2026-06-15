import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

const isCi = Boolean(process.env.CI);
const repoRoot = path.resolve(__dirname, '..');
const dbPath = path.join(repoRoot, 'data', 'e2e_rpg_assistant.db');

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: isCi,
  retries: isCi ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: 'http://127.0.0.1:4200',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  globalSetup: './e2e/global-setup.ts',
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
  webServer: [
    {
      command: 'uv run rpg-api',
      cwd: repoRoot,
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: !isCi,
      timeout: 120_000,
      env: {
        ...process.env,
        DATABASE_URL: `sqlite:///${dbPath.replace(/\\/g, '/')}`,
        CORS_ORIGINS: 'http://127.0.0.1:4200,http://localhost:4200',
      },
    },
    {
      command: 'npm run start -- --host 127.0.0.1 --port 4200 --proxy-config proxy.conf.json',
      cwd: path.join(repoRoot, 'web'),
      url: 'http://127.0.0.1:4200',
      reuseExistingServer: !isCi,
      timeout: 180_000,
    },
  ],
});
