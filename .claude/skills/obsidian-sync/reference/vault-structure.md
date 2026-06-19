# Vault 構造仕様（IA）

このスキルが読み書きする専用 Obsidian Vault の情報設計。逆流（Obsidian → Claude Code）が成立する
ように、**機械可読な frontmatter** と **一貫したフォルダ規約** を守ること。

## フォルダ規約

```
<vault>/
├── .obsidian/                  # Obsidian 設定（テーマ / Obsidian Git プラグイン）
├── .claude/skills/obsidian-sync/   # スキルのミラー（Web で Vault を add した際に利用可能に）
├── Projects/
│   └── <project>/              # 1 プロジェクト = 1 フォルダ
│       ├── index.md            # 母艦ノート(MOC)。逆流の入口
│       └── logs/
│           └── YYYY-MM-DD-<topic>.md   # セッションのアウトプット
└── Templates/                  # Obsidian 上で参照する雛形（任意）
```

- `<project>` 名はコードリポジトリ名に揃えるのを既定とする（設定 `projectMap` で上書き可）。
- ファイル名はケバブ/日本語可。logs は必ず `YYYY-MM-DD-` 接頭辞で時系列ソート可能にする。
- 同日に複数 log がある場合は `YYYY-MM-DD-<topic>-2.md` のように連番。

## frontmatter スキーマ

### `index.md`（プロジェクト母艦 / MOC）
```yaml
---
type: project
project: <name>
status: active        # active | paused | done
repo: <owner/repo or local path>
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [project]
---
```
本文セクション（見出しは固定にして逆流時に機械的に拾えるようにする）:
- `## 概要`
- `## 構成`（アーキ・主要コンポーネント）
- `## 現状`（今どこまで・次の一手）
- `## 未解決 / 課題`
- `## ログ`（`logs/` への wikilink 一覧。新しい順）

### `logs/*.md`（セッションログ）
```yaml
---
type: session-log
project: <name>
date: YYYY-MM-DD
phase: plan           # plan | build | verify | review
session: <session url or id>
repo: <owner/repo>
branch: <branch>
commit: <sha>
pr: <pr url>
tags: [log]
---
```
本文セクション（固定見出し）:
- `## やったこと`
- `## 検討内容`
- `## 検証結果`
- `## 確認結果`
- `## 決定事項`
- `## 関連`（`[[index]]` への戻りリンク、コミット/PR への外部リンク）

## リンク規約

- `index.md` の `## ログ` から各 log へ wikilink: `- [[logs/YYYY-MM-DD-<topic>|<topic>]]`。
- 各 log は `## 関連` で `[[index]]` に戻る。
- コードとの接続は **frontmatter（repo/branch/commit/pr）** を一次情報とし、本文には人間向けの
  リンク（PR URL 等）を添える。コード本体は Vault に置かない。

## 不変条件（壊さないこと）

- frontmatter の `type` と固定見出しは逆流の解析対象。勝手に変更しない。
- `index.md` の `updated` は集約のたびに当日へ更新する。
- 既存 log は追記ではなく原則新規ファイル（1 セッション = 1 log）。
