#!/usr/bin/env bash
# Capture une preuve visuelle (PNG) du visualiseur PDF pour une page donnée.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DOCUMENT_ID="${1:?Usage: capture-verification.sh DOCUMENT_ID PAGE [OUTPUT.png]}"
PAGE="${2:?Usage: capture-verification.sh DOCUMENT_ID PAGE [OUTPUT.png]}"
OUTPUT="${3:-/opt/cursor/artifacts/verification-page-${PAGE}.png}"

if [[ -f "$ROOT/.cursor/cache/frontend-toolchain.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.cursor/cache/frontend-toolchain.env"
elif [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
  export PATH="$NVM_DIR/versions/node/v$(tr -d '[:space:]' < "$ROOT/apps/web/.nvmrc")/bin:$PATH"
fi
export NG_CLI_ANALYTICS="${NG_CLI_ANALYTICS:-false}"

mkdir -p "$(dirname "$OUTPUT")"
cd "$ROOT/apps/web"
node ../../.cursor/scripts/capture-pdf-viewer.mjs "$DOCUMENT_ID" "$PAGE" "$OUTPUT"
echo "Screenshot: $OUTPUT"
