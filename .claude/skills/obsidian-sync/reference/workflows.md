# ワークフロー詳細

実行環境（ローカル / Web）の判定と、集約・逆流の手順。

## 実行環境の判定と Vault 解決

`scripts/resolve-vault.sh` を実行して Vault パスを得る。解決順:

1. 環境変数 `OBSIDIAN_VAULT_PATH` があればそれ。
2. `~/.claude/obsidian-sync.json` の `vaultPath`（ローカル）。
3. Web（リモート・使い捨てコンテナ）の場合: セッションに add 済みの Vault リポジトリを
   `.obsidian/` ディレクトリの存在で探索（カレントの親階層・兄弟ディレクトリを走査）。

解決できなければユーザーに Vault の場所を確認する（ローカルなら絶対パス、Web なら Vault リポジトリを
セッションへ add してもらう）。

判定の目安:
- ローカル = `OBSIDIAN_VAULT_PATH` か config の `vaultPath` が実在するフォルダ → 直接 read/write。
- Web = 上記が無く、`.obsidian/` を含むリポジトリがセッション内に存在 → Git 経由。

## A. 集約（Claude Code → Obsidian）

1. **環境判定 & Vault 解決**: `scripts/resolve-vault.sh`。Web は先に最新を pull。
2. **プロジェクト判定**: config `projectMap[<コードrepo名>]` → 無ければコード repo 名を既定に。
   どれにも当たらなければユーザーに確認。
3. **プロジェクトフォルダ確保**: `Projects/<project>/` が無ければ作成し、`templates/project-index.md`
   を埋めて `index.md` を生成（`created`/`updated` は当日、`repo` を記入）。
4. **ログ作成**: `templates/session-log.md` を埋めて `Projects/<project>/logs/YYYY-MM-DD-<topic>.md`
   を新規作成。frontmatter の repo/branch/commit/pr は実際の値を入れる:
   - `branch` = `git rev-parse --abbrev-ref HEAD`
   - `commit` = `git rev-parse --short HEAD`
   - `pr` = 分かれば PR URL（無ければ空）
   本文に「やったこと/検討内容/検証結果/確認結果/決定事項」を記述。
5. **index 更新**: `## 現状` を最新化、`## ログ` の先頭へ新 log の wikilink を追加、frontmatter
   `updated` を当日に。`status` が変わるなら更新。
6. **同期**:
   - ローカル: そのまま保存（Obsidian Git が auto-commit/push）。明示同期したいときのみ
     `scripts/sync-vault.sh "<message>"`。
   - Web: `scripts/sync-vault.sh "obsidian-sync: <project> <topic>"` で add/commit/push。

## B. 逆流（Obsidian → Claude Code）

1. **環境判定 & Vault 解決**: `scripts/resolve-vault.sh`。Web は先に最新を pull。
2. **読み込み**: `Projects/<project>/index.md` を読み、`## 現状`・`## 未解決 / 課題`・`## 構成` を把握。
   `## ログ` から直近数件の log を読む（新しい順）。各 log の `## 決定事項`・`## 検証結果` を重視。
3. **コンテキスト化**: 現状サマリ、確定済みの決定、既知の課題、コード位置（frontmatter の
   repo/branch/commit/pr）を短くまとめ、それを前提に修正計画/実装へ進む。
4. **修正後**: 作業が一段落したら A（集約）で新しい log を残し、決定や検証結果を更新する。

## プランモード（Web）での注意

- plan mode 中は **書き込み不可**（読み取りは可）。よって逆流はそのまま実行できるが、集約の
  ファイル書き込みは **ExitPlanMode 後** に行う。プラン段階の検討内容は、プラン確定後に
  `phase: plan` の log として残す。

## トリガー（ハイブリッド）の運用

- 手動: ユーザーの自然文指示で A/B を実行。
- 能動: 「プラン確定直後」「検証完了直後」に A の実行を提案・実行。
- フック（任意）: `hooks/vault-autosync.sh` を Stop/SessionEnd に登録すると Vault の未コミット変更を
  commit+push（内容は生成しない）。`settings.json` でオプトイン。
