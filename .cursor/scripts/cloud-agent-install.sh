#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap: COF2 PDFs, .env, SQLite schema.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PDF_DIR="$ROOT/data/pdfs"
mkdir -p "$PDF_DIR"

declare -A COF2_PDFS=(
  ["COF2_10_Mondanites_Et_Momies_web_v1a.pdf"]="1ebOAM2Vw16T_5i9lKT4-lqmy-TdLm5DL"
  ["COF2_07_Le_Dernier_Faelys_web_v0.pdf"]="1c4u-oOBWpcy7pFybxhVIYUesyZZDehEP"
  ["COF2_Mortelle_Xelys.pdf"]="1UZAZoqKrXnco38WKpw0-p2dgrqK7DnM6"
  ["COF2_Croissez_Et_Multipliez.pdf"]="1euEHqIoSDbl2nWODq1DryAlYgsFr0e7w"
  ["COF2_Retour_En_Grace.pdf"]="16qbUJEgh0Vw8uYRJrnrcgKrA9nFI-XmM"
)

download_pdfs() {
  for filename in "${!COF2_PDFS[@]}"; do
    dest="$PDF_DIR/$filename"
    if [[ -f "$dest" ]]; then
      echo "PDF already present: $filename"
      continue
    fi
    file_id="${COF2_PDFS[$filename]}"
    echo "Downloading $filename from Google Drive ($file_id)..."
    uv run gdown "https://drive.google.com/uc?id=${file_id}" -O "$dest"
  done
}

ensure_clojure() {
  if command -v clojure >/dev/null 2>&1; then
    echo "Clojure CLI: $(clojure --version)"
    return
  fi
  echo "Installing Clojure CLI..."
  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq rlwrap curl
  else
    apt-get update -qq
    apt-get install -y -qq rlwrap curl
  fi
  curl -fsSL https://github.com/clojure/brew-install/releases/latest/download/linux-install.sh \
    -o /tmp/linux-install.sh
  chmod +x /tmp/linux-install.sh
  if command -v sudo >/dev/null 2>&1; then
    sudo /tmp/linux-install.sh
  else
    /tmp/linux-install.sh
  fi
  rm -f /tmp/linux-install.sh
  echo "Clojure CLI: $(clojure --version)"
}

set_env_var() {
  local key="$1"
  local value="$2"
  local env_file="$3"
  if grep -q "^${key}=" "$env_file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
  else
    echo "${key}=${value}" >> "$env_file"
  fi
}

setup_env_file() {
  local env_file="$ROOT/.env"
  if [[ ! -f "$env_file" ]]; then
    cp "$ROOT/.env.example" "$env_file"
  fi
  set_env_var "RPG_PDF_MOMIE" "$PDF_DIR/COF2_10_Mondanites_Et_Momies_web_v1a.pdf" "$env_file"
  set_env_var "RPG_PDF_FAELYS" "$PDF_DIR/COF2_07_Le_Dernier_Faelys_web_v0.pdf" "$env_file"
}

ensure_clojure
download_pdfs
setup_env_file
uv run alembic upgrade head
echo "Cloud agent bootstrap complete."
