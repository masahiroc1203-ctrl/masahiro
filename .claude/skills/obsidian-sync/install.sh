#!/usr/bin/env bash
# install.sh — obsidian-sync スキルを配布する。
#
# 配布先:
#   1. ~/.claude/skills/obsidian-sync         （ローカルの全プロジェクトで利用可）
#   2. <vault>/.claude/skills/obsidian-sync   （Web で Vault を add した際に利用可。--vault 指定時）
#
# 使い方:
#   install.sh [--link] [--vault <vault_path>]
#     --link            コピーではなく symlink で配置（ローカル開発時に便利）
#     --vault <path>    指定 Vault リポジトリにもミラー配置（省略時は config の vaultPath を試す）
#
# 設定ファイル ~/.claude/obsidian-sync.json が無ければ雛形を作成する。

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="obsidian-sync"
USE_LINK=0
VAULT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --link) USE_LINK=1; shift ;;
    --vault) VAULT="${2:-}"; shift 2 ;;
    *) echo "未知の引数: $1" >&2; exit 1 ;;
  esac
done

place() {  # place <dest_parent_dir>
  local dest_parent="$1"
  local dest="$dest_parent/$NAME"
  mkdir -p "$dest_parent"
  rm -rf "$dest"
  if [ "$USE_LINK" -eq 1 ]; then
    ln -s "$SRC" "$dest"
    echo "linked: $dest -> $SRC"
  else
    cp -R "$SRC" "$dest"
    echo "copied: $dest"
  fi
}

# 実行権限を付与
chmod +x "$SRC"/scripts/*.sh "$SRC"/hooks/*.sh "$SRC"/install.sh 2>/dev/null || true

# 1. ローカルグローバル
place "$HOME/.claude/skills"

# 設定ファイルの雛形
CONFIG="$HOME/.claude/obsidian-sync.json"
if [ ! -f "$CONFIG" ]; then
  if [ -f "$SRC/obsidian-sync.example.json" ]; then
    cp "$SRC/obsidian-sync.example.json" "$CONFIG"
    echo "created config: $CONFIG （vaultPath / vaultRepo を編集してください）"
  fi
fi

# 2. Vault リポジトリへミラー
if [ -z "$VAULT" ] && command -v jq >/dev/null 2>&1 && [ -f "$CONFIG" ]; then
  VAULT="$(jq -r '.vaultPath // empty' "$CONFIG" 2>/dev/null || true)"
  VAULT="${VAULT/#\~/$HOME}"
fi
if [ -n "$VAULT" ] && [ -d "$VAULT" ]; then
  place "$VAULT/.claude/skills"
elif [ -n "$VAULT" ]; then
  echo "警告: 指定された Vault が見つかりません: $VAULT" >&2
fi

echo "done."
