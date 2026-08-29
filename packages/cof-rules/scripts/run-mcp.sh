#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export PATH="${DOTNET_ROOT}:$PATH"
export COF_RULES_DB="${COF_RULES_DB:-$ROOT/data/cof_rules.db}"
PROJECT="$ROOT/packages/cof-rules/src/CofRules.Mcp/CofRules.Mcp.csproj"
exec dotnet run --project "$PROJECT" --no-launch-profile "$@"
