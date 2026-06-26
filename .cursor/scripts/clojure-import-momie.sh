#!/usr/bin/env bash
# Réimporte le PDF Momie via la pipeline Clojure dans data/rpg_assistant.db.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PDF="${ROOT}/data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf"
DB="${ROOT}/data/rpg_assistant.db"

if [[ ! -f "$PDF" ]]; then
  echo "PDF missing: $PDF — run cloud-agent-install.sh first" >&2
  exit 1
fi

cd "$ROOT/packages/ingest-clj"
clojure -M:ingest import \
  --pdf "$PDF" \
  --campaign-id momie \
  --campaign-title "Mondanités et Momie" \
  --game-system cof2 \
  --db "$DB"
