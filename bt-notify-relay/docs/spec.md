# プロジェクト仕様書: PC-Android Bluetooth 通知連携システム (BT-Notify-Relay)

## 1. 概要
Windows PC で発生した通知（会議リマインダー、チャット、メール等）を Bluetooth 経由で Android スマートフォンへリアルタイム転送し、Android 標準通知として再発行するシステム。
Android 側の通知をスマートバンド公式アプリ（Mi Fitness、HUAWEI Health、Garmin Connect 等）の「アプリ通知転送」機能で拾わせることで、スマートバンド側の独自プロトコルを解析せずにPC通知・リマインドをウェアラブル端末へ届ける。

### 前提・対象環境
- **PC (送信側)**: Windows 10 / 11（Bluetooth 搭載、Android 端末と OS レベルでペアリング済み）
- **スマートフォン (中継側)**: Android 10 (API 29) 以上（推奨: Android 13 / API 33 以上）
- **ウェアラブル (受信側)**: Android のアプリ別通知転送に対応したスマートバンド / スマートウォッチ

---

## 2. システムアーキテクチャ

### データフロー
1. **検知 (PC)**: Windows Notification Listener API が対象アプリ（Outlook, Teams, Slack 等）のトースト通知を検知する。
2. **フィルタリング (PC)**: 許可リスト（アプリID・キーワード）および重複排除フィルタを通過した通知を JSON 化する。
3. **送信 (PC -> Android)**: Bluetooth Classic (RFCOMM) ソケット経由で、ペアリング済み Android 端末の専用 UUID サービスへ UTF-8 改行区切り JSON を送信する。
4. **受信・通知発行 (Android)**: フォアグラウンドサービス（常駐）が RFCOMM サーバーソケットで受信し、`NotificationManager` を用いてローカル通知を発行する。
5. **バンド転送 (Android -> Band)**: 既存のスマートバンド公式アプリが自作 Android アプリの通知を検知し、BLE 経由でスマートバンドへ転送する。

### 技術スタック選定
| コンポーネント | 採用技術 | 選定理由 |
| :--- | :--- | :--- |
| **PC アプリ** | **C# / .NET 8** (`net8.0-windows10.0.19041.0`)<br>WPF または WinForms（タスクトレイ常駐） | WinRT の `UserNotificationListener` と `RfcommDeviceService` を追加ドライバなしでネイティブ利用可能。 |
| **Android アプリ** | **Kotlin** / Jetpack Compose (UI)<br>Min SDK: 29 / Target SDK: 34 | `BluetoothServerSocket` と `ForegroundService` による安定したバックグラウンド待機が可能。 |
| **通信方式** | **Bluetooth Classic (RFCOMM / SPP)** | テキスト（JSON）のストリーム送信が安定しており、BLE GATT のペイロード長制限（MTU）を気にせず扱える。 |

---

## 3. 通信プロトコル仕様

- **サービス UUID**: `8ce255c0-200a-11e0-ac64-0800200c9a66`（PC・Android 双方で固定定義）
- **フレーミング**: UTF-8 エンコード、1メッセージ1行の改行区切り JSON（NDJSON / `\n` 終端）
- **キープアライブ**: 30秒間データ送信がない場合、PC 側から `ping` を送信し接続死活を監視する。

### メッセージスキーマ

#### 1. 通知転送 (`notification`) — PC -> Android
```json
{
  "type": "notification",
  "id": "win-notif-1024",
  "app_name": "Microsoft Teams",
  "title": "定例ミーティング (5分前)",
  "body": "15:30 から開始します",
  "timestamp": 1795760000
}
```

#### 2. 死活監視 (`ping` / `pong`) — 双方向

```json
{ "type": "ping", "timestamp": 1795760030 }
```

```json
{ "type": "pong", "timestamp": 1795760030 }
```

## 4. 機能要件

### 4.1 PC 側アプリケーション (`pc-sender`)

- **FR-PC-01: タスクトレイ常駐 & 接続状態表示**
  - システムトレイに常駐し、アイコンの色またはツールチップで「接続中 / 待機中（再接続中） / エラー」を表示する。
  - 右クリックメニューから「接続先デバイス選択」「テスト通知送信」「設定ファイルを開く」「終了」を操作できる。
- **FR-PC-02: Bluetooth 自動接続・再接続**
  - 設定ファイルに保存された Android 端末（Bluetooth アドレス / デバイス名）へ起動時に自動接続する。
  - スリープ復帰や Bluetooth 圏外からの復帰を検知した場合、5秒間隔（最大30秒の指数バックオフ）で自動再接続を試みる。
- **FR-PC-03: Windows 通知監視 (`UserNotificationListener`)**
  - OS の通知アクセス権限をリクエストし、新規トースト通知イベントを購読する。
  - 同一通知 ID の重複送信を防止する（直近 100 件の ID をメモリキャッシュ）。
- **FR-PC-04: フィルタリング機能 (`config.json`)**
  - `allowed_apps`: 転送を許可するアプリの AppUserModelID または表示名のリスト（空配列の場合は全アプリ対象）。
  - `exclude_keywords`: 転送を除外するキーワードリスト。
  - `quiet_hours`: 通知転送を停止する時間帯（例: `"23:00"` 〜 `"07:00"`）。

### 4.2 Android 側アプリケーション (`android-relay`)

- **FR-AND-01: RFCOMM サーバー常駐 (Foreground Service)**
  - `foregroundServiceType="connectedDevice"` を指定したサービスを起動し、固定 UUID で `listenUsingRfcommWithServiceRecord` を待機する。
  - クライアント切断時はソケットをクリーンアップし、即座に次の接続待機（`accept()`）へ戻る。
- **FR-AND-02: ローカル通知の発行**
  - `notification` メッセージ受信時、専用通知チャンネル（`pc_relay_channel` / 重要度: `IMPORTANCE_HIGH`）で通知を発行する。
  - 通知タイトルに `[app_name] title`、本文に `body` をセットし、スマートバンド側で送信元アプリが判別できるようにする。
  - 通知のグループ化を無効化（または個別通知 ID を付与）し、連続受信時もスマートバンド側で1件ずつ振動・表示されるようにする。
- **FR-AND-03: 管理画面 UI**
  - 現在のサービス稼働状態・PC との接続ステータス表示。
  - 「サービス開始 / 停止」トグルボタン。
  - 「ローカルテスト通知を発行」ボタン（スマートバンド側公式アプリの通知連携設定を行う際のトリガー用）。
  - バッテリー最適化（Doze モード）除外設定画面へのショートカット導線。

## 5. 権限・OS 制約への対応

### Android Manifest 必須権限

- `android.permission.BLUETOOTH_CONNECT`（Android 12+ 実行時権限リクエスト必須）
- `android.permission.POST_NOTIFICATIONS`（Android 13+ 実行時権限リクエスト必須）
- `android.permission.FOREGROUND_SERVICE`
- `android.permission.FOREGROUND_SERVICE_CONNECTED_DEVICE`
- `android.permission.RECEIVE_BOOT_COMPLETED`（端末再起動時のサービス自動起動用・任意）

### Windows 側制約

- `UserNotificationListener` はパッケージ化されたアプリ（MSIX）または適切なアプリ ID を持つ環境で動作するため、開発時は Windows App SDK / コンソールパッケージ構成、または `UserNotificationListener.GetDefault()` の権限取得ステータス（`UserNotificationListenerAccessStatus.Allowed`）を必ず検証する。

## 6. リポジトリ構成案

```text
bt-notify-relay/
├── spec.md                     # 本仕様書
├── pc-sender/                  # Windows C# (.NET 8) プロジェクト
│   ├── BtNotifySender.csproj
│   ├── Program.cs              # エントリポイント・タスクトレイ制御
│   ├── BluetoothClient.cs      # RFCOMM 接続・再接続・送信キュー管理
│   ├── NotificationWatcher.cs  # UserNotificationListener 監視・フィルタ
│   └── config.json             # 接続先デバイス名・フィルタ設定
└── android-relay/              # Android Kotlin プロジェクト
    └── app/src/main/
        ├── AndroidManifest.xml
        └── java/com/example/btnotifyrelay/
            ├── MainActivity.kt         # 権限要求・ステータスUI・テスト通知
            ├── BtRelayService.kt       # ForegroundService & RFCOMM サーバー
            └── NotificationHelper.kt   # 通知チャンネル作成・通知発行
```

## 7. 実装マイルストーン（段階的開発手順）

1. **Phase 1: Android 側コア実装**
  - `MainActivity` での権限取得（Bluetooth / 通知）とテスト通知発行ボタンの実装。
  - この時点でスマートバンド公式アプリ（Mi Fitness 等）を開き、本アプリの通知転送を ON にする。
2. **Phase 2: Bluetooth RFCOMM 疎通確認**
  - Android の `BtRelayService` と PC の `BluetoothClient` を実装し、PC から送ったテスト JSON が Android 通知経由でスマートバンドに届くことを確認する。
3. **Phase 3: PC 側通知フックと自動再接続**
  - `NotificationWatcher` と `config.json` によるアプリフィルタリング、およびスリープ復帰時の自動再接続処理を実装する。

---

## 8. 実装メモ（2026-11-27 追記。ここより上は Gemini で作成した仕様のまま）

実際のフォルダ構成と、上の仕様との違い。詳しくは `../README.md` の「Gemini 版からの変更点」。

```text
bt-notify-relay/
├── README.md                   # 試し方・設定・トラブル対処
├── docs/spec.md                # 本仕様書
├── pc-sender/                  # Windows C# (.NET 8) トレイ常駐アプリ
│   ├── Program.cs              # エントリポイント・タスクトレイ制御
│   ├── AppConfig.cs            # config.json の読み込み
│   ├── Protocol.cs             # 通信形式 (1行1JSON)
│   ├── BluetoothClient.cs      # RFCOMM 接続・再接続・ping/pong・送信の保留
│   ├── ScheduleMonitor.cs      # 予定・リマインダーの監視
│   ├── OutlookCalendar.cs      # クラシック版 Outlook (COM) から予定取得
│   ├── IcsParser.cs            # ICS の読み取り
│   ├── ReminderClock.cs        # 時刻計算 (静かな時間帯・曜日)
│   ├── NotificationWatcher.cs  # Windows 通知の監視 (MSIX 化するまで未使用)
│   └── config.json
├── pc-sender.Tests/            # PC 側の単体テスト (xUnit)
└── android-relay/              # Android Kotlin プロジェクト (Gradle)
    └── app/src/main/java/com/example/btnotifyrelay/
        ├── MainActivity.kt
        ├── BtRelayService.kt
        ├── RelayProtocol.kt    # 通信形式 (単体テスト対象)
        └── NotificationHelper.kt
```

- **PC の通知元**: Windows のトースト通知 (FR-PC-03) は MSIX が必要なため未接続。代わりに Outlook / ICS の予定、自作リマインダー、クイックタイマーを送る
- **静かな時間帯の設定名**: `quiet_hours` ではなく `quiet_hours_start` / `quiet_hours_end`
- **接続先**: デバイス名の部分一致のみ (FR-PC-02 のアドレス指定、FR-PC-01 の「接続先デバイス選択」は未実装)
- **キープアライブ**: PC は 30 秒ごとに ping を送り、pong が 75 秒返らなければ再接続する。どちらの側も ping を受けたら pong を返す
- **Android**: UI は Jetpack Compose ではなく View。Target SDK は 35。サーバーソケットは開いたままにし、新しい接続が来たら古い接続を閉じる
