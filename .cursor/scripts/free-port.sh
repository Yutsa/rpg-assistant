#!/usr/bin/env bash
# Libère un port TCP en tuant le(s) processus qui l'écoutent.
set -euo pipefail

PORT="${1:?Usage: free-port.sh PORT}"

collect_pids() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null \
      | rg ":${PORT}\\b" \
      | rg -o 'pid=[0-9]+' \
      | cut -d= -f2 \
      | sort -u
    return
  fi

  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | sort -u
    return
  fi

  if command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "${PORT}" 2>/dev/null | tr ' ' '\n' | rg '^[0-9]+$' | sort -u
    return
  fi

  echo "No port inspection tool found (ss/lsof/fuser)" >&2
  exit 1
}

mapfile -t PIDS < <(collect_pids || true)

if ((${#PIDS[@]} == 0)); then
  echo "Port ${PORT} is free"
  exit 0
fi

echo "Freeing port ${PORT} (PID(s): ${PIDS[*]})"
kill "${PIDS[@]}" 2>/dev/null || true
sleep 1

mapfile -t REMAINING < <(collect_pids || true)
if ((${#REMAINING[@]} > 0)); then
  echo "Force-killing port ${PORT} (PID(s): ${REMAINING[*]})"
  kill -9 "${REMAINING[@]}" 2>/dev/null || true
  sleep 1
fi

mapfile -t STILL_THERE < <(collect_pids || true)
if ((${#STILL_THERE[@]} > 0)); then
  echo "Port ${PORT} still in use (PID(s): ${STILL_THERE[*]})" >&2
  exit 1
fi

echo "Port ${PORT} is free"
