#!/usr/bin/env bash
# vault-autosync.sh — 任意の Stop / SessionEnd フック。
# Vault に未コミット変更があれば commit+push して取りこぼしを防ぐ（内容生成はしない）。
#
# settings.json での登録例（オプトイン）:
#   {
#     "hooks": {
#       "Stop": [
#         { "hooks": [ { "type": "command",
#           "command": "$HOME/.claude/skills/obsidian-sync/hooks/vault-autosync.sh" } ] }
#       ]
#     }
#   }
#
# フックの stdin に渡る JSON は使用しない。常に静かに終了する（失敗してもセッションは止めない）。

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC="$SCRIPT_DIR/../scripts/sync-vault.sh"

# stdin を読み捨て（フックは JSON を渡してくる）
cat >/dev/null 2>&1 || true

VAULT="$("$SCRIPT_DIR/../scripts/resolve-vault.sh" 2>/dev/null)" || exit 0
[ -d "$VAULT/.git" ] || exit 0   # git 管理でなければ何もしない（ローカルは Obsidian Git に委譲）

"$SYNC" "obsidian-sync: autosync ($(date +%F\ %T))" "$VAULT" >/dev/null 2>&1 || true
exit 0
