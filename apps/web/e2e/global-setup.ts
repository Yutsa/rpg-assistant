import { execSync } from 'node:child_process';
import path from 'node:path';

const repoRoot = path.resolve(__dirname, '../..');

export default async function globalSetup(): Promise<void> {
  execSync('uv run python scripts/seed_e2e_db.py', {
    cwd: repoRoot,
    stdio: 'inherit',
    env: {
      ...process.env,
    },
  });
}
