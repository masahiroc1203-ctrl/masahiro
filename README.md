# Claude 成果物台帳 (claude-ledger)

Claude で作った成果物を、**進捗状況・使用モデル・使用トークン・推定コスト**でまとめて管理するツールです。

- **自動集計** — Claude Code のセッションログ (`~/.claude/projects/**/*.jsonl`) を解析し、
  セッションごとの使用モデル・入出力トークン・キャッシュ読み書き・推定コストを算出します。
- **手動台帳** — 進捗ステータスやリンクなどログに残らない情報は `deliverables.yaml` で管理し、
  セッションIDで紐付けます。
- **ダッシュボード** — 両者を突き合わせた HTML (`docs/dashboard.html`) を生成します。

## 使い方

```bash
# 1. ログを集計（data/sessions.json を生成）
python3 tools/claude_ledger.py scan

# 2. 成果物を台帳に登録（セッションIDは8桁の前方一致でOK）
python3 tools/claude_ledger.py add "新機能の設計" --status 進行中 --sessions 68d1c943 --tags 設計

# 3. ダッシュボードを生成
python3 tools/claude_ledger.py build

# scan → build をまとめて
python3 tools/claude_ledger.py all

# ターミナルで要約を見る
python3 tools/claude_ledger.py report
```

必要なもの: Python 3.11+ と PyYAML (`pip install pyyaml`)。

## 台帳フォーマット

`deliverables.yaml` を直接編集しても構いません。

```yaml
deliverables:
  - id: claude-ledger
    title: Claude 成果物管理ダッシュボード
    status: レビュー中        # 未着手 / 進行中 / レビュー中 / 保留 / 完了 / アーカイブ
    tags: [ツール, 可視化]
    link: https://github.com/...
    notes: 一行メモ
    updated: 2026-08-06
    sessions:                # 前方一致で紐付け。複数可
      - 68d1c943
```

`sessions` に紐付けなかったセッションは、ダッシュボードの「未紐付けセッション」に一覧されるので、
そこから台帳へ割り当てていく運用になります。

## 集計の注意点

- **重複排除** — Claude Code のログは 1 回の API 応答を複数行（thinking / text / tool_use）に
  分割して書き出し、**同じ `usage` を繰り返し記録**します。素朴に合計するとトークンが 2〜3 倍に
  なるため、`message.id` で重複排除しています。
- **コストは概算** — Anthropic の公開価格に基づく試算で、実際の請求額とは一致しません。
  キャッシュ書込は 5 分 TTL = 入力単価 ×1.25、1 時間 TTL = ×2.0、キャッシュ読込 = ×0.1 で計算。
  Sonnet 5 の導入価格など期間限定料金は、セッションの実行日で自動的に切り替わります。
- **価格表にないモデル** はコスト未計上とし、ダッシュボード末尾に一覧表示します。
  料金改定時は `tools/claude_ledger.py` の `PRICING` を更新してください。

## 構成

| パス | 役割 |
| --- | --- |
| `tools/claude_ledger.py` | CLI 本体（集計・台帳操作） |
| `tools/ledger_html.py` | ダッシュボードのレンダラ |
| `deliverables.yaml` | 手動管理の成果物台帳 |
| `data/sessions.json` | `scan` が生成する集計結果 |
| `docs/dashboard.html` | 生成されるダッシュボード |
