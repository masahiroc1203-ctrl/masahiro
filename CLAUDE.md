# HIIT Weekly

## プロジェクト概要
週ごとに強化する部位を決めて、その部位のHIITメニューを **お手本アニメ（または登録した動画）を見ながら** タバタ式タイマーで行う、スマホ向けWebアプリ（PWA）。
ユーザーの要望：①週ごとに強化部位を選んでメニューを決めたい ②種目名だけでは覚えられないので動画と一緒に運動したい ③スマホのタバタ式アプリのようにメニューを選んで実行したい。

## 技術スタック
- 素の HTML / CSS / JavaScript（ES Modules）。**ビルド工程・実行時の依存パッケージなし**（GitHub Pages でそのまま配信）
- 保存：localStorage（キー `hiit-weekly:v1`、中身は `js/store.js` の `blank()` 参照）
- オフライン：`sw.js`（Service Worker）
- テスト：`node:test`（Node 20 以上）／ブラウザ通し確認：Playwright（任意・開発時のみ）

## ローカルで動かす
```bash
git clone https://github.com/masahiroc1203-ctrl/masahiro.git
cd masahiro
git checkout claude/hiit-menu-app-wxte6y   # PR #12 マージ後は main
npm start                 # http://localhost:8080 （依存インストール不要）
```

| コマンド | 内容 |
| --- | --- |
| `npm start` | 開発サーバー（`scripts/serve.mjs`、Python不要）。`PORT=3000 npm start` でポート変更 |
| `npm test` | ロジックのテスト（タイマー・週計算・動画URL・データ整合性・アニメの床めり込み） |
| `npm run lint` | ESLint（未使用変数・未定義の名前など）。初回は npx が eslint を取得 |
| `npm run check` | test ＋ lint。**コミット前に必ず実行** |
| `npm run smoke` | スマホサイズのブラウザで全画面・ワークアウト・メニュー作成などを通し確認。スクショは `.screenshots/`。初回のみ `npm i -D playwright && npx playwright install chromium` |
| `/dev/poses.html` | 全種目のアニメをコマ送りで一覧（`?ids=squat,lunge&n=8` で絞り込み、`&static` でライブ再生なし） |

## ディレクトリ構成
```
index.html / manifest.webmanifest / sw.js / icons/
css/app.css              全スタイル（トークンは :root、ダークは prefers-color-scheme と [data-theme]）
js/app.js                ハッシュルーター（#/, #/menus, #/menu/:id, #/edit/:id, #/exercises, #/exercise/:id, #/history, #/settings）
js/views/*.js            各画面。{ title, sub, back, actions, cls, html, mount(root, ctx) } を返す
js/player.js             ワークアウト画面（全画面オーバーレイ）
js/engine.js             タイムライン生成・Session（DOM非依存）
js/pose.js               棒人間の骨格計算：順運動学＋2リンクIK、キーフレーム補間（DOM非依存）
js/figure.js             SVG描画・共通 rAF ループ・表示範囲の自動フィット（motionBox）
js/store.js              保存データ・週（月曜はじまり）の計算・おすすめ部位
js/ui.js                 esc / icon / figSlot+mountFigures / stepper / toast / openSheet / confirmSheet
js/video.js              YouTube・mp4 URL の解釈と埋め込みURL
js/audio.js              ビープ（Web Audio）・音声読み上げ・バイブ・画面スリープ防止
js/data/                 exercises.js（35種目）/ menus.js（15プリセット）/ parts.js（5部位）
tests/                   node:test
scripts/                 serve.mjs（開発サーバー）/ smoke.mjs（ブラウザ通し確認）
dev/poses.html           ポーズ確認ページ
```

## 開発ルール
- UI文言・コードコメントは日本語（既存に合わせる）。コメントは「なぜ」を短く
- ビルドツール・フレームワーク・外部CDNを入れない（オフライン動作と Pages 直配信のため）
- DOM に依存しないロジック（engine / pose / store / video）を変えたら `tests/` にテストを足す
- ユーザー入力を HTML 文字列に入れるときは必ず `esc()`
- ブラウザ標準の `confirm()` / `alert()` は使わない → `confirmSheet()` / `toast()`（iPhoneのホーム画面アプリや埋め込み表示で問題になるため）
- 画面の `mount()` は毎回新しい root 要素に対して呼ばれる（`app.js` が作り直す）ので、root へのイベント登録は重複しない。`document` や `window` に登録したら必ず外す
- **静的ファイルを追加・改名したら `sw.js` の `ASSETS` を更新し、配布物を変えたら `VERSION` を上げる**（上げないとインストール済み端末に古いキャッシュが残る）
- 種目の追加：`js/data/exercises.js` にオブジェクトを追加 → `/dev/poses.html?ids=新ID` で見た目確認 → `npm test`（床めり込み・IK到達を検査）
- 色はすべて CSS トークン経由。`color-mix()` を使うときは直前に代替の単色を書く（iOS 16.2 未満対策）

---

## Handoff
<!-- updated: 2026-09-29 -->

### タスク概要
スマホで使う「週替わり・部位別HIIT」アプリ。v1 はクラウドの Claude Code セッションで実装済み（PR #12・下書き、ブランチ `claude/hiit-menu-app-wxte6y`）。次はマージ → GitHub Pages 公開 → 実機での調整。

### 決定した方針
- ネイティブアプリではなく PWA。公開は GitHub Pages（Settings → Pages → Deploy from a branch → `main` / `(root)`、`.nojekyll` 追加済み）。公開URL予定：https://masahiroc1203-ctrl.github.io/masahiro/
- 「動画と一緒に運動」は、まず **自前の棒人間アニメ**（全35種目・オフライン可・権利問題なし）で実現。実写動画は **ユーザーが種目ごとに YouTube / mp4 のURLを登録** する方式。アプリ側で動画を選んで埋め込まない（実在確認できないURLを入れないため）
- 週は月曜はじまり。週ごとに強化部位（複数可）を保存し、最後に鍛えてから一番間が空いた部位を「おすすめ」
- メニュー＝種目リスト×周回。`work / rest / laps / lapRest`（lapRest=0 なら周の切れ目も通常の rest）。最後のワークの後に休憩は入れない
- 記録：ワーク区間を半分以上やったら1本。途中終了は運動10秒以上のときだけ記録
- データは端末内のみ（アカウント・サーバーなし）。機種変更は設定画面の JSON バックアップ

### 実装ステップ
- [x] ✅ 骨格計算とアニメ（`js/pose.js`, `js/figure.js`）、35種目データ（`js/data/exercises.js`）
- [x] ✅ タイマーエンジン（`js/engine.js`）とプレイヤー（`js/player.js`）：準備/ワーク/レスト/周間休憩、3・2・1音、音声ガイド、一時停止・スキップ、左右交代の合図、スリープ防止
- [x] ✅ 画面：ホーム（今週の部位・実施日）/ メニュー一覧・詳細（時間調整）・作成 / 種目一覧・詳細 / 記録 / 設定
- [x] ✅ 動画URL登録（`js/video.js`）とワークアウト中の動画⇄アニメ切替、YouTube検索ボタン
- [x] ✅ PWA（manifest・`sw.js`・アイコン）、ライト/ダーク
- [x] ✅ テスト19件・lint・ブラウザ通し確認（`npm run smoke` 24項目）・CI（`.github/workflows/ci.yml`）
- [ ] PR #12 を確認してマージ
- [ ] GitHub Pages を有効化し、iPhone / Android の実機で確認：ビープ音・音声・バイブ・画面スリープ防止・ホーム画面追加・オフライン起動
- [ ] 実機で分かりにくい種目のアニメがあればキーフレームを調整（`/dev/poses.html`）
- [ ] よく使う種目に YouTube 動画URLを登録してみて、ワークアウト中の見え方を確認

### 技術スタック・環境
- 言語/FW：素の JavaScript（ES Modules）、HTML、CSS。Node 20 以上（テスト・開発サーバー用）
- 主要ライブラリ：なし（開発時のみ ESLint 9 を npx、Playwright は任意）
- ディレクトリ構成：上の「ディレクトリ構成」参照

### 注意事項
- **iOS の音**：タップ操作の中で `unlockAudio()` を呼ばないと鳴らない（`app.js` の `startWorkout` で呼んでいる）。マナーモード中は Web Audio のビープが鳴らない場合がある
- **Service Worker** は「キャッシュを返して裏で更新」。変更が端末に出ないときは `VERSION` を上げるか、ページを2回再読み込み。`npm start` のサーバーは `no-store` なので開発中は影響なし
- **アニメの座標系**：viewBox 120×100、床の線 y=94、床に接する関節は y=92（`at(x)` の既定値）。角度は 0=真下・90=右（前）・180=真上。FK と IK が混在するフレーム間は角度に換算して補間するため、足が床をくぐることがある → `npm test` が検出する（マウンテンクライマーで一度発生し、IK指定に変えて解決）
- 正面ビュー（`view: 'front'`）の IK は `b` の絶対値で膝のふくらみを縮めて奥行きを表現している（0.2〜0.6）
- 表示時は各種目の1サイクル全体が収まる範囲に viewBox を合わせる（`figure.js` の `motionBox`）ので、枠の大きさに関係なく大きく描かれる
- ルーティングはハッシュ。プレイヤーを開くと `history.pushState` で1段積み、端末の戻るボタンで終了確認を出す
- **Claude.ai のプレビュー（アーティファクト）** では `confirm()`・ファイルのダウンロード・YouTube埋め込み・Service Worker が使えない。プレビューは `npx esbuild@0.24.0 js/app.js --bundle --format=iife --minify` で1本にまとめ、`css/app.css` と `index.html` の body と合わせて1つのHTMLにして公開した：https://claude.ai/artifact/C211ZY8HcULfSKecsNuHLg
- リポジトリ直下の `test`（1バイトの空ファイル）は既存のもの。アプリとは無関係なので触っていない

### 未解決事項（CLIで判断が必要）
- 次回最初にやること：PR #12 をマージして GitHub Pages を有効化し、スマホ実機で一通り動かす
- 検討候補（未決定・ユーザーと相談）：曜日ごとの週間計画（例：月水金に何をやるか）、部位の自動ローテーション、ウォームアップ／クールダウンの自動追加、BGM、記録のカレンダー表示
