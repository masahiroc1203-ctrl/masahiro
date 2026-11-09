# NASバックアップ（Android アプリ）

Android スマホの写真・動画を、**LS720D などの NAS の共有フォルダへ直接**バックアップするアプリです。
Raspberry Pi や PC は必要ありません。

```
 Android スマホ ──Wi-Fi (SMB)──▶ LS720D の共有フォルダ\SmartphoneBackup\
```

## できること

- 写真・動画を月ごとに一覧表示し、**まだ NAS に無いものだけ**を表示・選択できる
- **撮影年月ごとにフォルダ分け**して保存（`papa\2026\2026-11\IMG_0001.jpg`）
- **画面を消しても送信が続く**（通知に進み具合を表示。通知から停止もできる）
- 途中で Wi-Fi が切れても、**送信済みの続きから再開**
- **写真の位置情報も含めた元のファイル**をそのまま保存
- 同じ名前で中身が違うファイルは `IMG_0001 (1).jpg` として保存（上書きしない）
- Web 版（`nas-backup` サーバー）と同じフォルダ構成なので併用できる

対応: Android 10 以降

## インストール

1. GitHub のリポジトリの「Actions」→「nas-backup-android」→ 最新の実行結果を開く
2. 下の「Artifacts」にある `nas-backup-android-apk` をダウンロードして展開する
3. 中の `nas-backup-android.apk` をスマホに送る（Google ドライブ、USB ケーブルなど）
4. スマホで APK を開いてインストールする
   - 「提供元不明のアプリ」の確認が出たら、開いたアプリ（ファイル / Chrome など）に「この提供元のアプリを許可」する
   - Google Play プロテクトの警告が出た場合は「詳細」→「インストールする」

> GitHub で Release を作成すると、APK が Release にも添付されます。

## 初期設定

アプリを開くと設定画面が出ます。LS720D 側の準備は [LS720D での使い方](../docs/LS720D.md#1-ls720d-側の準備) を参照してください。

| 項目 | 入力例 | 説明 |
| --- | --- | --- |
| NASのIPアドレス | `192.168.1.50` | NAS Navigator2 などで確認 |
| 共有フォルダ名 | `share` | LS720D の共有フォルダ |
| 保存先フォルダ | `SmartphoneBackup` | 共有フォルダの中に自動で作られる |
| ユーザー名 / パスワード | `backup` | アクセス制限をしていなければ空 |
| 保存先フォルダ名（家族で使うとき） | `papa` | 人ごとにフォルダを分ける |

「接続テスト」で ✓ が出たら「保存」を押します。

## 使い方

1. スマホを家の Wi-Fi につなぐ
2. アプリを開くと、まだバックアップしていない写真・動画が月ごとに表示される
3. 写真をタップして選ぶ（「この月を選択」「すべて選択」も使える）
4. 「バックアップ開始」をタップ
5. 送信中はほかのアプリを使ったり画面を消したりしても大丈夫です

## うまくいかないとき

| 表示 | 対処 |
| --- | --- |
| NASに接続できません | スマホが家の Wi-Fi につながっているか、IP アドレスが正しいか確認 |
| ユーザー名またはパスワードが違います | LS720D のユーザー名・パスワードを確認 |
| 共有フォルダが見つかりません | 共有フォルダ名を確認（保存先フォルダではなく、LS720D の共有フォルダの名前） |
| 共有フォルダに書き込む権限がありません | LS720D のアクセス制限で、そのユーザーに「読み書き」を許可 |
| NASからの応答がありません | LS720D がスリープしていないか確認 |

## アップデート時の注意

署名鍵を設定していない場合、ビルドごとに署名が変わるため、新しい版をインストールするときは**古いアプリをアンインストールしてから**インストールしてください（NAS の設定は入れ直しになります。NAS に保存したファイルは消えません）。

上書きでアップデートできるようにしたい場合は、署名鍵を作ってリポジトリの Secrets に登録します（Java の `keytool` が使える PC で 1 回だけ行います）。

```sh
keytool -genkeypair -keystore nasbackup.keystore -alias nasbackup -keyalg RSA -keysize 2048 -validity 36500 -dname "CN=NAS Backup"
base64 -w0 nasbackup.keystore    # 表示された文字列をコピー
```

GitHub のリポジトリの「Settings」→「Secrets and variables」→「Actions」で次の 2 つを登録します。

| 名前 | 値 |
| --- | --- |
| `NASBACKUP_KEYSTORE_BASE64` | 上でコピーした文字列 |
| `NASBACKUP_KEYSTORE_PASSWORD` | keytool で決めたパスワード |

> 署名鍵ファイルは大切に保管し、リポジトリには入れないでください。

## 開発

```sh
./gradlew :core:test          # 保存処理のテスト
./gradlew :app:assembleDebug  # APK (Android SDK が必要)
```

実際の SMB サーバー（Samba）を使ったテストも実行できます（Ubuntu / Debian）。

```sh
./scripts/start-test-samba.sh
SMB_TEST_HOST=127.0.0.1 SMB_TEST_PORT=1445 SMB_TEST_SHARE=share \
SMB_TEST_USER=smbtest SMB_TEST_PASSWORD=secret ./gradlew :core:test
```

| フォルダ | 内容 |
| --- | --- |
| `core/` | NAS への保存処理（SMB 接続・フォルダ分け・重複判定・再開）。Android に依存しないので PC でテストできる |
| `app/` | Android アプリ（画面・写真の読み込み・バックグラウンド送信） |
