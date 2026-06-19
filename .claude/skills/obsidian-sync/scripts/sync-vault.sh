#!/usr/bin/env bash
# sync-vault.sh — Vault の変更を git で commit/push する（主に Web 経路で使用）。
#
# 使い方:
#   sync-vault.sh "<commit message>" [vault_path]
#
# vault_path 省略時は resolve-vault.sh で解決。Vault が git リポジトリでなければ何もしない
# （ローカルは Obsidian Git が同期するため通常は呼ばなくてよい）。

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MSG="${1:-obsidian-sync: update vault}"
VAULT="${2:-}"

if [ -z "$VAULT" ]; then
  VAULT="$("$SCRIPT_DIR/resolve-vault.sh")" || exit 1
fi

cd "$VAULT" || { echo "sync-vault: cd 失敗: $VAULT" >&2; exit 1; }

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "sync-vault: $VAULT は git リポジトリではありません（ローカルなら Obsidian Git に委譲）。" >&2
  exit 0
fi

git add -A
if git diff --cached --quiet; then
  echo "sync-vault: 変更なし。"
  exit 0
fi

git commit -m "$MSG" >/dev/null
echo "sync-vault: committed."

# push（ネットワーク失敗時のみ指数バックオフで最大4回）
branch="$(git rev-parse --abbrev-ref HEAD)"
delay=2
for attempt in 1 2 3 4 5; do
  if git push origin "$branch"; then
    echo "sync-vault: pushed to origin/$branch."
    exit 0
  fi
  if [ "$attempt" -lt 5 ]; then
    echo "sync-vault: push 失敗。${delay}s 後に再試行..." >&2
    sleep "$delay"
    delay=$(( delay * 2 ))
  fi
done

echo "sync-vault: push に失敗しました。コミットはローカルに残っています。" >&2
exit 1
