#!/usr/bin/env bash
# resolve-vault.sh — 専用 Obsidian Vault のパスを解決して標準出力に1行で返す。
#
# 解決順:
#   1. 環境変数 OBSIDIAN_VAULT_PATH
#   2. ~/.claude/obsidian-sync.json の vaultPath
#   3. Web(リモート): セッション内で .obsidian/ を含むディレクトリを探索
#
# 見つかれば絶対パスを echo して exit 0。見つからなければ stderr にヒントを出して exit 1。

set -uo pipefail

CONFIG="${HOME}/.claude/obsidian-sync.json"

# --- JSON から値を取り出す（jq → python3 → grep の順でフォールバック） -------------
json_value() {
  local file="$1" key="$2"
  [ -f "$file" ] || return 1
  if command -v jq >/dev/null 2>&1; then
    jq -r --arg k "$key" '.[$k] // empty' "$file" 2>/dev/null
  elif command -v python3 >/dev/null 2>&1; then
    python3 - "$file" "$key" <<'PY' 2>/dev/null
import json, sys
try:
    with open(sys.argv[1]) as f:
        print(json.load(f).get(sys.argv[2], "") or "")
except Exception:
    pass
PY
  else
    # 素朴なフォールバック: "key": "value"
    sed -n "s/.*\"$key\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$file" | head -n1
  fi
}

is_vault() { [ -n "${1:-}" ] && [ -d "$1/.obsidian" ]; }

# --- 1. 環境変数 ----------------------------------------------------------------
if [ -n "${OBSIDIAN_VAULT_PATH:-}" ] && [ -d "${OBSIDIAN_VAULT_PATH}" ]; then
  echo "${OBSIDIAN_VAULT_PATH}"
  exit 0
fi

# --- 2. 設定ファイル ------------------------------------------------------------
CFG_PATH="$(json_value "$CONFIG" vaultPath || true)"
# ~ を展開
CFG_PATH="${CFG_PATH/#\~/$HOME}"
if [ -n "$CFG_PATH" ] && [ -d "$CFG_PATH" ]; then
  echo "$CFG_PATH"
  exit 0
fi

# --- 3. Web: .obsidian を含むディレクトリを探索 ---------------------------------
# カレント・親・兄弟ディレクトリを浅く走査（深掘りしすぎない）。
search_roots=()
cur="$(pwd)"
search_roots+=("$cur" "$(dirname "$cur")" "$(dirname "$(dirname "$cur")")")
# よくあるリモートのワークスペース親
for d in /home /workspace /root /repos; do
  [ -d "$d" ] && search_roots+=("$d")
done

found=""
for root in "${search_roots[@]}"; do
  [ -d "$root" ] || continue
  # root 直下とその子で .obsidian を探す（maxdepth 3）
  while IFS= read -r obs; do
    cand="$(dirname "$obs")"
    if is_vault "$cand"; then found="$cand"; break; fi
  done < <(find "$root" -maxdepth 3 -type d -name ".obsidian" 2>/dev/null)
  [ -n "$found" ] && break
done

if [ -n "$found" ]; then
  echo "$found"
  exit 0
fi

# --- 解決失敗 -------------------------------------------------------------------
{
  echo "obsidian-sync: Vault を解決できませんでした。"
  echo "  ローカル: 環境変数 OBSIDIAN_VAULT_PATH を設定するか、${CONFIG} の vaultPath に絶対パスを記入。"
  echo "  Web: 専用 Vault リポジトリ(.obsidian/ を含む)をこのセッションに add してください。"
} >&2
exit 1
