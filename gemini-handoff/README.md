# gemini-handoff

Claude Code の使用上限 (5時間枠 / 週枠) が **残り 8%** になったら、ロックされる前に作業内容を自動で保存し、
そのまま **Gemini CLI に渡せる引き継ぎファイル** (`<プロジェクト>/.handoff/HANDOFF.md`) を作ります。

## 仕組み

```
Claude Code の status line (使用率 rate_limits を受け取る)
   │  残り ≤ 8%
   ├─▶ ① 会話ログ + git の状態から HANDOFF.md を自動生成 (LLM 不使用なので確実)
   └─▶ ② 「保留中」の印を置く
                │
Stop / UserPromptSubmit hook
   └─▶ ③ Claude に「HANDOFF.md の要約欄を書いて」と 1 回だけ依頼
        (目的 / 完了したこと / 進行中 / 次にやること / 注意点)

   残り ≤ 3%            → スナップショットを再保存 (要約は保持)
   上限到達でロック      → StopFailure hook (rate_limit) が最後の状態を再保存

gemini-resume  →  HANDOFF.md を渡して Gemini CLI を起動
```

HANDOFF.md の中身:

1. **Gemini への指示** (実ファイルを確認してから再開すること、作業ログを残すこと)
2. **Claude による要約** (③ で Claude が書く欄)
3. **自動スナップショット** — 最初の依頼、最近の発言、Claude の最後の応答、TODO/タスク、編集したファイル、実行したコマンド、`git status` / diff / 直近のコミット
4. **Gemini 作業ログ** — Gemini が追記する欄 (Claude に戻るときに使える)

再生成しても「Claude による要約」と「Gemini 作業ログ」は消えません。過去の版は `.handoff/history/` に残ります (20 世代)。

## インストール (Claude Code を使うマシンで)

必要なもの: Python 3、Claude.ai のサブスクリプション (Pro / Max など。使用率は status line にしか渡されないため)。

```bash
git clone <このリポジトリ>
cd masahiro/gemini-handoff
./install.sh            # しきい値を変えるなら ./install.sh --threshold 10
```

その後 **Claude Code を再起動** (または `/hooks` を一度開く) すると有効になります。

インストーラがすること:

- `~/.claude/gemini-handoff/` にスクリプトをコピー
- `~/.claude/settings.json` に statusLine と hook (Stop / UserPromptSubmit / StopFailure) を追加 (変更前の内容は `settings.json.bak-日時` に保存)
  - すでに使っている statusLine があれば、その表示はそのまま残し、警告だけ 2 行目に出します
  - 既存の hook はそのまま残ります
- `/handoff` コマンドを `~/.claude/commands/handoff.md` に追加
- `~/.local/bin` が PATH にあれば `gemini-resume` をリンク

元に戻す: `./install.sh --uninstall`

## 使い方

| やりたいこと | 方法 |
|---|---|
| 自動で保存 | 何もしなくてよい。残り 8% で保存され、status line に `⚠ 上限間近: Gemini 用の引き継ぎを保存済み` と出ます |
| 今すぐ手動で保存 | Claude Code で `/handoff` (メモを付けるなら `/handoff テストがまだ`) |
| Gemini で続きをやる | プロジェクト内で `gemini-resume` (Gemini CLI のオプションも渡せます: `gemini-resume -m gemini-2.5-pro`) |
| Gemini の Web 版に渡す | `.handoff/HANDOFF.md` を添付するか、中身を貼り付ける |
| Claude に戻る (リセット後) | `claude --resume <セッションID>` (HANDOFF.md に記載) で再開し、「`@.handoff/HANDOFF.md` の Gemini 作業ログを読んで続きを」と頼む |

Gemini CLI のインストール: `npm install -g @google/gemini-cli`

## 設定 (`~/.claude/gemini-handoff/config.json`)

| キー | 既定 | 説明 |
|---|---|---|
| `threshold_remaining` | `8` | 残り何%で引き継ぎを作り、Claude に要約を書かせるか |
| `final_threshold_remaining` | `3` | 残り何%でスナップショットをもう一度保存するか |
| `windows` | `["five_hour","seven_day"]` | 監視する枠。どちらか残りの少ない方で判定 |
| `ask_claude_summary` | `true` | `false` にすると Claude に要約を頼まない (自動スナップショットのみ) |
| `update_gemini_md` | `false` | `true` にするとプロジェクトの `GEMINI.md` に `@./.handoff/HANDOFF.md` を追記し、素の `gemini` 起動でも読み込まれる |
| `handoff_dir` | `.handoff` | 保存先 |
| `wrapped_statusline` | (自動) | インストール前の statusLine コマンド |

一時的にしきい値を変える: 環境変数 `GEMINI_HANDOFF_THRESHOLD=15`

## 注意

- `.handoff/` には会話の抜粋と差分が入ります。コミットしたくない場合はプロジェクトの `.gitignore` に `.handoff/` を追加してください。
- 自動検知は **ターミナルの Claude Code** で status line が動いているときだけ働きます。claude.ai/code (Web / アプリ) のクラウドセッションでは status line が動かないので、`/handoff` を手動で実行し、`.handoff/` をコミット & push して手元で `gemini-resume` してください。
- API キー (従量課金) で使っている場合は使用上限の情報がないため、自動保存は動きません (`/handoff` は使えます)。
- 要約を書かせるのに使用量を少し使います。足りなくなりそうならしきい値を上げてください。
- 動作ログ: `~/.claude/gemini-handoff/state/logs/handoff.log`
