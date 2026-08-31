#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export PATH="${DOTNET_ROOT}:$PATH"
export COF_RULES_DB="${COF_RULES_DB:-$ROOT/data/cof_rules.db}"
PROJECT="$ROOT/src/CofRules.Mcp/CofRules.Mcp.csproj"
if [[ ! -f "$COF_RULES_DB" ]]; then
  dotnet run --project "$ROOT/src/CofRules.Cli/CofRules.Cli.csproj" --no-launch-profile -- import --db "$COF_RULES_DB"
fi
exec dotnet run --project "$PROJECT" --no-launch-profile "$@"
