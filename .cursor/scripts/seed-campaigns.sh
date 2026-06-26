#!/usr/bin/env bash
# Importe les 5 PDF COF2 de référence si la base est vide (idempotent).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DB="${ROOT}/data/rpg_assistant.db"
PDF_DIR="${ROOT}/data/pdfs"

campaign_count() {
  uv run python - <<'PY' 2>/dev/null || echo 0
import sqlite3
from pathlib import Path

db = Path("data/rpg_assistant.db")
if not db.is_file():
    print(0)
    raise SystemExit
conn = sqlite3.connect(db)
try:
    print(conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0])
finally:
    conn.close()
PY
}

import_pdf() {
  local pdf="$1"
  local campaign_id="$2"
  local title="$3"
  if [[ ! -f "$pdf" ]]; then
    echo "PDF missing, skipping ${campaign_id}: ${pdf}" >&2
    return 0
  fi
  echo "Importing ${campaign_id} (${title})..."
  uv run rpg-ingest raw extract "$pdf" \
    --campaign-id "$campaign_id" \
    --campaign-title "$title" \
    --game-system cof2 \
    --skip-compare-lanes
}

cd "$ROOT"

existing="$(campaign_count)"
if [[ "${existing}" -gt 0 ]]; then
  echo "Campaigns already seeded (${existing} in DB), skipping import."
  exit 0
fi

echo "No campaigns in DB — seeding COF2 reference PDFs..."

import_pdf "${PDF_DIR}/COF2_10_Mondanites_Et_Momies_web_v1a.pdf" \
  momie "Mondanités et Momie"
import_pdf "${PDF_DIR}/COF2_07_Le_Dernier_Faelys_web_v0.pdf" \
  dernier-faelys "Le Dernier Faelys"
import_pdf "${PDF_DIR}/COF2_Mortelle_Xelys.pdf" \
  mortelle-xelys "Mortelle Xélys"
import_pdf "${PDF_DIR}/COF2_Croissez_Et_Multipliez.pdf" \
  croissez-et-multipliez "Croissez et multipliez"
import_pdf "${PDF_DIR}/COF2_Retour_En_Grace.pdf" \
  retour-en-grace "Retour en grâce"

echo "Campaign seed complete ($(campaign_count) campaigns)."
