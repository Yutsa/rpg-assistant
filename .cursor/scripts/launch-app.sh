#!/usr/bin/env bash
# Point d'entrée unique pour agents : campagnes + stack dev (API + Angular).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WEB_PORT="${WEB_PORT:-4200}"

bash "$ROOT/.cursor/scripts/seed-campaigns.sh"
bash "$ROOT/.cursor/scripts/dev-stack.sh" restart

echo ""
echo "Application prête : http://127.0.0.1:${WEB_PORT}/"
echo "API docs        : http://127.0.0.1:${API_PORT:-8000}/docs"
