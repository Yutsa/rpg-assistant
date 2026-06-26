#!/usr/bin/env bash
# Démarre ou arrête la stack dev (API + Angular) pour vérification manuelle.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMUX_CONF="${TMUX_CONF:-/exec-daemon/tmux.portal.conf}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-4200}"
API_SESSION="${API_SESSION:-rpg-api-server}"
WEB_SESSION="${WEB_SESSION:-rpg-web-server}"

tmux_cmd() {
  if [[ -f "$TMUX_CONF" ]]; then
    tmux -f "$TMUX_CONF" "$@"
  else
    tmux "$@"
  fi
}

load_nvm() {
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  # shellcheck disable=SC1091
  [[ -s "$NVM_DIR/nvm.sh" ]] && . "$NVM_DIR/nvm.sh"
}

nvm_node_bin_dir() {
  load_nvm
  local version
  version="$(tr -d '[:space:]' < "$ROOT/apps/web/.nvmrc")"
  nvm install "$version" >/dev/null
  nvm use "$version" >/dev/null
  echo "$NVM_DIR/versions/node/v${version}/bin"
}

ensure_node() {
  local bin_dir
  bin_dir="$(nvm_node_bin_dir)"
  export PATH="${bin_dir}:$PATH"
  cd "$ROOT/apps/web"
  node -v
}

free_port() {
  bash "$ROOT/.cursor/scripts/free-port.sh" "$1"
}

stop_sessions() {
  tmux_cmd kill-session -t "$API_SESSION" 2>/dev/null || true
  tmux_cmd kill-session -t "$WEB_SESSION" 2>/dev/null || true
}

stop_stack() {
  echo "Stopping dev stack..."
  stop_sessions
  free_port "$API_PORT" || true
  free_port "$WEB_PORT" || true
  echo "Dev stack stopped."
}

wait_for_url() {
  local url="$1"
  local label="$2"
  for _ in $(seq 1 90); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "${label} ready: ${url}"
      return 0
    fi
    sleep 2
  done
  echo "Timeout waiting for ${label} (${url})" >&2
  return 1
}

start_stack() {
  echo "Starting dev stack..."
  stop_stack

  export PATH="$HOME/.local/bin:$PATH"
  cd "$ROOT"

  tmux_cmd new-session -d -s "$API_SESSION" -c "$ROOT" -- "${SHELL:-bash}" -lc \
    "export PATH=\"$HOME/.local/bin:\$PATH\"; uv run rpg-api"

  local web_bin
  web_bin="$(nvm_node_bin_dir)"
  export PATH="${web_bin}:$PATH"

  ensure_node
  cd "$ROOT/apps/web"
  npm install --no-audit --no-fund

  WEB_START="export PATH=\"${web_bin}:\$PATH\"; export NG_CLI_ANALYTICS=false; cd \"$ROOT/apps/web\"; npm start -- --host 127.0.0.1 --port ${WEB_PORT}"

  tmux_cmd new-session -d -s "$WEB_SESSION" -c "$ROOT/apps/web" -- "${SHELL:-bash}" -lc "$WEB_START"

  wait_for_url "http://127.0.0.1:${API_PORT}/health" "API"
  wait_for_url "http://127.0.0.1:${WEB_PORT}" "Web"

  echo ""
  echo "Stack prête pour vérification manuelle :"
  echo "  API  → http://127.0.0.1:${API_PORT}/docs"
  echo "  Web  → http://127.0.0.1:${WEB_PORT}"
}

status_stack() {
  local api web
  api=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${API_PORT}/health" 2>/dev/null || echo "000")
  web=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${WEB_PORT}" 2>/dev/null || echo "000")
  echo "API (${API_PORT}): ${api}"
  echo "Web (${WEB_PORT}): ${web}"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${API_PORT}" -sTCP:LISTEN 2>/dev/null || true
    lsof -iTCP:"${WEB_PORT}" -sTCP:LISTEN 2>/dev/null || true
  fi
}

case "${1:-start}" in
  start) start_stack ;;
  stop) stop_stack ;;
  restart) stop_stack; start_stack ;;
  status) status_stack ;;
  *)
    echo "Usage: dev-stack.sh {start|stop|restart|status}" >&2
    exit 1
    ;;
esac
