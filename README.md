# HIIT Weekly（週替わり・部位別HIIT）

週ごとに「今週はどこを鍛えるか」を決めて、その部位のHIITメニューを **お手本アニメを見ながら** タバタ式タイマーで行うスマホ向けWebアプリです。
ホーム画面に追加すればアプリのように使え、オフラインでも動きます。

## できること

- **今週の強化部位を決める** … 全身・有酸素 / 下半身 / 腹筋・体幹 / 上半身 / 背中・姿勢 から選択（複数可）。しばらくやっていない部位を「おすすめ」表示
- **部位別メニュー** … 15種類のプリセット（タバタ4分〜12分）。運動・休憩・周回・周間休憩の秒数を自由に調整
- **自分のメニューを作る** … 35種目から選んで並べ替え、時間を決めて保存
- **お手本アニメと一緒に運動** … 全35種目に、スポーツウェア姿の人物のループアニメ付き。ワーク中は「いまの種目」、休憩中は「次の種目」を大きく表示
- **タバタ式タイマー** … 準備 → ワーク → レスト を色で切り替え（オレンジ／緑／青）。3・2・1のビープ音、「レスト。次は〇〇」の音声ガイド、バイブ、画面スリープ防止、一時停止・スキップ。ビープ音と音声の音量は設定で5段階に調整可
- **動画も使える** … 種目ごとに YouTube などの解説動画URLを登録すると、ワークアウト中にアニメの代わりに動画を表示（ワンタップで切替）。YouTube検索ボタン付き
- **記録** … 今週の実施日・回数・運動時間、直近4週の部位バランス、週ごとの履歴

## スマホで使う

1. 公開URL（下記「公開のしかた」参照）をスマホのブラウザで開く
2. **iPhone（Safari）**：共有ボタン →「ホーム画面に追加」
   **Android（Chrome）**：メニュー（︙）→「ホーム画面に追加」
3. ホーム画面のアイコンから起動

> 記録・自作メニュー・動画URLは端末のブラウザ内（localStorage）に保存されます。機種変更時は「設定 → バックアップを保存／読み込む」を使ってください。

## Android アプリ（APK）として使う

`android/` は、この Web アプリを APK に同梱して表示する Android アプリです（公開サーバー不要・オフラインで動く）。
Web 版のファイル（index.html・css・js・icons）はビルド時にコピーされるので、アプリだけのために二重に直す必要はありません。
WebView に無い「音声ガイド・画面スリープ防止・バックアップの保存／読み込み・心拍計の受信」は Android 側の機能を使います（`window.HiitNative`）。

```bash
cd android
# JDK は Android Studio 同梱のものを使う（Git Bash の例）
export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"
./gradlew assembleDebug    # → app/build/outputs/apk/debug/app-debug.apk
```

スマホへの入れ方（どちらか）：

- **USB**：スマホの開発者向けオプションで USB デバッグを有効にし、`adb install -r app/build/outputs/apk/debug/app-debug.apk`
- **ファイルを送る**：APK を Google ドライブなどに置き、スマホで開いてインストール（「提供元不明のアプリ」の許可が必要）

> アプリ版のデータは Web 版（ブラウザ）とは別に保存されます。移すときは「設定 → バックアップを保存／読み込む」。
> APK はこのPCのデバッグ用の鍵で署名されます。別のPCでビルドした APK は上書きインストールできず、入れ直すとデータが消えるので、先にバックアップを取ってください。

### 心拍計をつなぐ（Android アプリ版のみ）

Bluetooth の心拍計（Xiaomi Smart Band の「心拍数を共有」、胸ベルト型など）を登録すると、ワークアウト中に今の心拍数が出ます。

1. バンド側で **設定 → 心拍数を共有** をオンにする（共有中はバンドの画面で他の操作ができません）
2. アプリの **設定 → 心拍計 → 心拍計をさがす** でバンドを選ぶ。初回は「付近のデバイス」の許可を求められます
3. 心拍数が届くと登録されます。次からは、ワークアウトを始めると自動でつながります（運動の前にバンド側の共有をオンにしておく）

> パソコンのブラウザで画面だけ確かめたいときは、URL に `?hrsim=1` を付けると擬似の心拍計が出ます（例：`http://localhost:8080/index.html?hrsim=1#/settings`）。

## 公開のしかた（GitHub Pages）

ビルド不要の静的サイトなので、リポジトリのルートをそのまま公開できます。

1. GitHub のリポジトリ画面 → **Settings → Pages**
2. **Build and deployment → Source** を「Deploy from a branch」、Branch を `main` / `/(root)` にして Save
3. 数分後に `https://masahiroc1203-ctrl.github.io/masahiro/` で開けます

## パソコンで動かす・続きを開発する

```bash
git clone https://github.com/masahiroc1203-ctrl/masahiro.git
cd masahiro
npm start          # http://localhost:8080 を開く（依存インストール不要・Node.js 20以上）
npm run check      # テスト＋lint
npm run smoke      # ブラウザで通し確認（初回のみ: npm i -D playwright && npx playwright install chromium）
```

ES Modules を使っているため、`index.html` を直接ダブルクリックではなく、上記のように開発サーバー経由で開いてください。
同じWi-FiのスマホからPCのIPアドレス（例 `http://192.168.0.10:8080`）で開けば実機でも確認できます（画面スリープ防止とオフライン対応は https の公開URL か localhost でのみ動きます）。

**Claude Code で続きを作業する場合**：開発ルール・設計判断・現在の進み具合は [`CLAUDE.md`](CLAUDE.md) にまとめてあります。`claude` を起動して `/start` で再開、作業の区切りで `/done` を実行すると `CLAUDE.md` の Handoff 欄が更新されます。

## ファイル構成

```
index.html              画面の枠（タブバー）
css/app.css             スタイル（ライト／ダーク対応）
js/app.js               ルーター
js/views/*.js           各画面（ホーム・メニュー・種目・記録/設定）
js/player.js            ワークアウト画面（タイマー＋お手本）
js/engine.js            タイムライン生成・タイマー状態（DOM非依存）
js/pose.js              人物の骨格計算（順運動学＋2リンクIK、手・つま先の向き）
js/figure.js            人物のSVG描画（体の形・服・重ね順）とアニメーションループ
js/store.js             保存データ・週の計算
js/audio.js             ビープ音・音声読み上げ・バイブ・スリープ防止
js/hr.js                心拍計（Bluetooth）からの心拍数の受け取り
js/data/exercises.js    種目データ（説明文とアニメのキーフレーム）
js/data/menus.js        プリセットメニュー
sw.js                   オフライン用サービスワーカー
dev/poses.html          開発用：全種目のポーズを一覧表示
scripts/                開発サーバー（serve.mjs）とブラウザ通し確認（smoke.mjs）
tests/                  node:test によるテスト
CLAUDE.md               開発ルールと引き継ぎメモ（Claude Code 用）
android/                Android アプリ版（WebView で上のファイルを表示する入れ物）
```

## 種目を追加するには

`js/data/exercises.js` にオブジェクトを1つ追加します。アニメはキーフレームの配列で、各フレームに

- `hip: [x, y]` … 腰の位置（画面は 120×100、床は y=94。床に接する点は y=92）
- `t` … 胴体の向き（0=真下, 90=右, 180=真上）
- `a1`/`a2`（腕）, `l1`/`l2`（脚） … `[上側の角度, 下側の角度]`、または `at(x, y)` で手先・足先の位置を指定（IKで肘・膝を自動計算）

を書きます。`npm start` のあと `http://localhost:8080/dev/poses.html?ids=新しいID` で動きを確認し、`npm test` でデータの整合性（床へのめり込み等）をチェックできます。

## 注意

HIITは強度の高い運動です。体調に合わせて無理のない範囲で行い、持病のある方は医師に相談してください。

## テスト時間の記録

| 日付 | 内容 | 件数 | 所要時間 |
| --- | --- | --- | --- |
| 2026-09-30 | `npm run check`（test＋lint） | 19件 | 4.9秒 |
| 2026-10-02 | `npm run check`（test＋lint）。人物の描画に変更、テスト2件追加 | 21件 | 5.8秒 |
| 2026-10-02 | `npm run check`（test＋lint）。音量調整を追加、テスト1件追加 | 22件 | 5.1秒 |
| 2026-10-07 | `npm run check`（test＋lint）。心拍計の受信を追加、テスト3件追加 | 25件 | 4.5秒 |
