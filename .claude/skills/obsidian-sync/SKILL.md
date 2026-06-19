---
name: obsidian-sync
description: >-
  Claude Code のセッション成果（検証結果・確認結果・検討内容・決定事項などコード以外のアウトプット）を
  専用 Obsidian Vault に集約（Claude Code → Obsidian）し、既存アプリ/コードを修正する際に過去の決定・
  検証履歴を Vault から読み戻す（Obsidian → Claude Code）ための双方向連携スキル。
  「Obsidian にまとめて」「セッションを記録して」「Obsidian から <app> の情報を引っ張ってきて」
  「前回の検討内容を読み戻して」等の依頼、またはプラン確定後・検証完了後のフェーズ転換時に使う。
---

# obsidian-sync

Claude Code ↔ 専用 Obsidian Vault の双方向連携。コードは各コードリポジトリに残し、**コード以外の
知識（検証・確認・検討・決定）** を Vault に集約し、後から読み戻して修正作業に活かす。

## 前提アーキテクチャ

- Vault は **Claude Code 専用の private GitHub リポジトリ**。Obsidian 側は Obsidian Git で同期。
- 運用: **プラン＝Web（Git 経由）／コーディング＝ローカル CLI・デスクトップ（フォルダ直接）**。
- 構造: **1 プロジェクト = 1 フォルダ**（`Projects/<app>/index.md` ＋ `logs/`）。
- スキルは実行環境を判定し、ローカル=フォルダ直接 / Web=Git 経由 を自動で切り替える。

## このスキルの 2 つの振る舞い

### A. 集約（Claude Code → Obsidian）
セッションのアウトプットを Vault に書き出す。手順の詳細は `reference/workflows.md` の「集約」を参照。
要点:
1. `scripts/resolve-vault.sh` で Vault パスを解決。
2. 対象プロジェクトを判定（設定の `projectMap` / コード repo 名、不明なら確認）。
3. `Projects/<project>/` を確保（無ければ `templates/project-index.md` から index 生成）。
4. `logs/YYYY-MM-DD-<topic>.md` を `templates/session-log.md` から作成し、検討/検証/確認/決定/
   コードリンク（repo・branch・commit・PR）を記入。
5. `index.md` の現状・更新日・logs リンクを更新。
6. 同期: ローカル=直接書込（Obsidian Git に委譲）／Web=`scripts/sync-vault.sh` で commit+push。

### B. 逆流（Obsidian → Claude Code）
既存プロジェクトの文脈を Vault から読み戻す。手順の詳細は `reference/workflows.md` の「逆流」を参照。
要点:
1. `scripts/resolve-vault.sh` で Vault を解決（Web は事前に pull）。
2. `Projects/<project>/index.md` ＋ 直近 logs を読む。
3. 現状・決定事項・既知の課題・コード位置（repo/branch）を要約してコンテキスト化し、修正計画/実装へ。

## 起動の仕方（ハイブリッド）

- **手動**: 自然文（「Obsidian にまとめて」「Obsidian から引っ張ってきて」）または Skill 起動。
- **能動**: フェーズ転換時（プラン確定後・検証完了後）に集約を提案・実行する。
- **フック（任意）**: `hooks/vault-autosync.sh` を Stop/SessionEnd に登録すると、Vault の未コミット
  変更を自動 commit+push（内容生成はしない取りこぼし防止用）。`settings.json` でオプトイン。

## 重要な制約

- **プランモード（Web）では書き込み不可**。逆流（読み取り）は plan mode でも可。集約の書き込みは
  ExitPlanMode 後に行う。
- コード本体は Vault に置かない。frontmatter の repo/branch/commit/pr で実コードへ常にリンクする。

## 参照ファイル（必要時に読む）

- `reference/vault-structure.md` — フォルダ規約・frontmatter スキーマ・リンク規約（IA 仕様）。
- `reference/workflows.md` — 集約/逆流の詳細手順、Web/ローカルの経路分岐。
- `templates/` — `project-index.md` / `session-log.md` の雛形。
- `scripts/resolve-vault.sh` / `scripts/sync-vault.sh` — Vault 解決・同期。
- `install.sh` — `~/.claude/skills/` と Vault リポジトリへの配布。
