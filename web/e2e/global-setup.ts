import { execSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const dbPath = path.join(repoRoot, "data", "e2e_test.db");

export default async function globalSetup() {
  const databaseUrl = `sqlite:///${dbPath}`;
  execSync(`uv run python web/e2e/seed_db.py --database-url "${databaseUrl}"`, {
    cwd: repoRoot,
    stdio: "inherit",
    env: { ...process.env, DATABASE_URL: databaseUrl },
  });
}
