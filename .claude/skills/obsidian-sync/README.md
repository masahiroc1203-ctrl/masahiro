# obsidian-sync

Claude Code ↔ 専用 Obsidian Vault の双方向連携スキル。コード以外のアウトプット（検証・確認・検討・
決定）を Vault に集約し、修正時に読み戻す。スキルの中身は `SKILL.md` を参照。

## セットアップ（初回のみ）

### 1. 専用 Vault を作る
1. Obsidian で **新規 Vault** を作成（例: `claude-code-vault`）。個人 Vault とは分ける。
2. その Vault フォルダで `git init` し、**private** な GitHub リポジトリとして push。
3. Obsidian のコミュニティプラグイン **Obsidian Git** を入れ、auto-commit/auto-push（pull）を有効化。
   - 例: backup interval / pull on startup を設定し、Web の push を自動取り込み。
4. Vault 直下に `Projects/` を作成（最初の集約時に自動生成されるので任意）。

### 2. スキルを配布
リポジトリ正本（`masahiro/.claude/skills/obsidian-sync`）から:

**macOS / Linux / Git Bash:**
```bash
# ローカル全プロジェクト向け（+ Vault リポジトリにもミラー）
.claude/skills/obsidian-sync/install.sh --vault ~/ObsidianVaults/claude-code-vault
```

**Windows（PowerShell）:**
```powershell
# cmd / PowerShell だけで完結（bash 不要）
.\.claude\skills\obsidian-sync\install.ps1 -Vault "C:/Users/<you>/ObsidianVaults/claude-code-vault"
```
> 実行ポリシーで止まる場合は次のように一時許可で実行:
> `powershell -ExecutionPolicy Bypass -File .\.claude\skills\obsidian-sync\install.ps1 -Vault "<vault>"`

> ⚠️ Windows での **実行時**（スキルの `resolve-vault.sh` / `sync-vault.sh`）は bash が必要です。
> Git for Windows 同梱の **Git Bash** が入っていれば Claude Code がそれを使って実行します。

`~/.claude/obsidian-sync.json`（Windows は `%USERPROFILE%\.claude\obsidian-sync.json`）が雛形から作られるので編集:

```json
{
  "vaultPath": "~/ObsidianVaults/claude-code-vault",
  "vaultRepo": "<owner>/<vault-private-repo>",
  "projectMap": { "<コードrepo名>": "<Vault上のProject名>" }
}
```

### 3.（任意）自動同期フックを有効化
取りこぼし防止に Stop/SessionEnd で Vault を自動 commit+push したい場合、`settings.json` に登録:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command",
        "command": "$HOME/.claude/skills/obsidian-sync/hooks/vault-autosync.sh" } ] }
    ]
  }
}
```

## 使い方

- 集約: 「Obsidian にまとめて」「このセッションを記録して」
- 逆流: 「Obsidian から <app> の情報を引っ張ってきて」「前回の検討を読み戻して」

## 運用イメージ

- **プラン = Web**: Vault リポジトリをセッションに add → 逆流で過去の決定を読む → プラン確定後に
  `phase: plan` の log を書いて push（Obsidian Git が手元へ pull）。
- **コーディング = ローカル**: Vault フォルダを直接読み書き。検証/確認結果を log に残し index を更新。
