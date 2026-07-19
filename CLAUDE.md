# masahiro — 住環境エネルギー分析

## プロジェクト概要

家の温度データ・電力使用量（部屋別/時間別）・ガス使用量の関係を分析し、効率的な住環境を維持するための改善アクションを提示するツール。分析本体は `home_energy/`、入力データは `data/`、レポートとグラフは `output/` に出力される。使い方・データ形式は `home_energy/README.md` を参照。

## コーディング規約（要点）

- Python: PEP 8、型ヒント必須、f-string、マジックナンバー禁止（定数は `config.py`）
- 1ファイル1責務、300行超えたら分割を検討
- 設定（Config）と状態（State）を分離。エラーは握りつぶさない
- コミットメッセージ: `種別: 内容`（feat / fix / refactor / docs / chore、日本語OK）
- 秘密情報（WiFiパスワード・APIキー・HEMSの認証情報）はコミットしない

## Handoff
<!-- updated: 2026-07-19 (ローカルCLIセッションでHEMS調査・ECHONET Lite検証済み) -->

### タスク概要

温度×電力×ガスの関係分析ツールの基盤はリモートセッションで構築済み（PR #9、ブランチ `claude/home-temperature-energy-gas-analysis-offkm6`）。次はローカルにある実データ（HEMSの部屋別・時間別電力など）の投入と、家の端末からの自動取得の構築。

### HEMS調査結果（2026-07-19 ローカルセッションで確定）

- HEMS端末は **NEC IG1002STC/SF**（ソーラーフロンティアOEMのNECクラウド型HEMS。AiSEG2想定は誤り）
- クラウドサービス（solar-frontier-hems.com）は **2023-06-30にサービス終了済み** → 当初想定の「HEMSエクスポートCSV→convert_hems.py」経路は存在しない
- 代替経路を検証済み: **ECHONET LiteでLANから直接ポーリング可能**（`home_energy/discover_echonet.py` で探索、実データ取得に成功）
  - `192.168.11.3` — 計測ユニット: 分電盤メータリング(0x0287, **6回路**) + 住宅用太陽光発電(0x0279)
  - `192.168.11.2` — コントローラ(0x05FF) = IG1002情報収集装置本体
  - `192.168.11.7` — 0x0135(空気清浄器とみられる)
  - 取得確認済みEPC: 0xC0 マスタ積算電力量 / 0xC6 マスタ瞬時電力（売電時は負値）/ 0xB3 回路別積算電力量リスト / 0xB5 回路別瞬時値リスト / 太陽光 0xE0 瞬時発電・0xE1 積算発電
  - **重要**: 計測ユニットは送信元UDPポート3610宛にしか応答しない（エフェメラルポートからのGetは無応答）。ポーリング実装は `bind(("0.0.0.0", 3610))` 必須
  - 単位・係数（0xD3 係数, 0xC2 積算有効桁等）の解釈と、6回路←→部屋名のマッピングは未確定（分電盤ブレーカー表示かHEMS設定情報で要確認）

### 決定した方針

- 分析手法: 度日回帰（HDD基準18°C・CDD基準24°C）。電力は外気温で暖房域/中間域/冷房域に3分割し、中間域平均をベース電力とする。ガスは月次HDD回帰で床暖房分と給湯・調理ベースを分離
- 電力入力は `data/electricity_hourly.csv`（`datetime,room,kwh` ロング形式）を優先。あれば部屋別内訳・時間帯プロファイル・部屋別冷房感応度を算出し、日次合計も自動集計。なければ `data/electricity.csv`（日次）にフォールバック
- 住まいモデル: 暖房=ガス温水床暖房メイン＋たまにエアコン（電力の暖房感応度は補助分）／冷房=各部屋エアコン／1F: LDK吹き抜け（冷房効率・温度成層に注意）／2F: 浴室・寝室・書斎・室内干しカウンター
- 契約: 電気=中部電力ミライズ（カテエネ）、ガス=東邦ガス（Club TOHOGAS）。単価は `config.py` の定数（要実値更新）
- グラフのラベルは英語（実行環境に日本語フォントがない場合の文字化け対策）。部屋名も英数字推奨
- 現在の `data/` は `generate_sample_data.py` によるサンプル。実データで置き換える

### 実装ステップ

- [x] 分析パイプライン基盤（度日回帰・ベース電力・快適性・レポート/グラフ出力）
- [x] 部屋別・時間別データ対応（room_analysis.py）とサンプルデータでの動作確認
- [x] ローカル環境でパイプライン動作確認（Windows / Python 3.14 / pandas 3.0.3）
- [x] HEMS端末の型番を確認（NEC IG1002STC/SF。クラウド終了によりCSVエクスポート不可と判明）
- [x] ECHONET Lite探索スクリプト `home_energy/discover_echonet.py` を追加し、LANから回路別データ取得を実証
- [ ] ~~HEMSエクスポートCSVの変換スクリプト `convert_hems.py`~~ → 廃止。代わりにECHONET Liteポーリング収集スクリプト `home_energy/poll_hems.py` を実装（0xB3積算値を定期取得→差分で時間別kWh→`electricity_hourly.csv` 蓄積。0xD3係数・0xC2桁数の解釈を含む）
- [ ] 6回路と部屋名のマッピングを確定（分電盤のブレーカー表示を確認）
- [ ] 温度ロガーの実データを `temperature.csv` 形式（date, indoor_temp_c, outdoor_temp_c）に変換
- [ ] ガス検針値（Club TOHOGAS/検針票）を `gas.csv` に転記
- [ ] `python analyze.py` で実データレポートを生成し、サンプル前提の注記を外す
- [ ] `config.py` の料金単価（ELECTRICITY_YEN_PER_KWH / GAS_YEN_PER_M3）を契約実値に更新
- [ ] （自動化・方式A）常時稼働機（RasPi等、または常用PC）で `poll_hems.py` を定期実行し日次で git push
- [ ] （拡張候補）太陽光発電データ(0x0279)も取得できるため、発電・売電の分析を追加検討

### 技術スタック・環境

- 言語/FW: Python 3.11+（pandas / matplotlib / numpy、`home_energy/requirements.txt`）
- ディレクトリ構成:
  - `home_energy/config.py` — 定数（パス・基準温度・単価）
  - `home_energy/analyze.py` — エントリポイント（読み込み→分析→出力）
  - `home_energy/regression.py` — 単回帰ユーティリティ
  - `home_energy/room_analysis.py` — 部屋別・時間別分析
  - `home_energy/report.py` — Markdownレポート整形・推奨アクション生成
  - `home_energy/plots.py` — グラフ出力（Agg backend）
  - `home_energy/generate_sample_data.py` — サンプルデータ生成（実データ導入後は不要）
- 実行: `cd home_energy && python analyze.py` → `output/report.md` と PNG

### 注意事項

- 回帰はサンプル数が `MIN_REGRESSION_SAMPLES`（5）未満なら None を返し、レポートには「未算出」と出る仕様（少データでの誤解防止）
- pandas 3.0 で動作確認済み。`DatetimeIndex.dayofyear` は Index を返すので numpy 演算前に `to_numpy()` が必要（既に対応済み）
- `data/electricity_hourly.csv` があると `electricity.csv` は読まれない
- 温度と電力は日付の inner join。期間が一致しないと行が減るので実データ投入時は期間を確認
- 自動取得の方式（リモートセッションで整理済み）: A=RasPi等でLANポーリング→git push（完全自動・推奨）／B=端末からエクスポート→Google Drive（半自動）／C=手動アップ。BルートWi-SUNは全戸合計のみで部屋別要件に合わない

### 未解決事項

- 6回路←→部屋名(用途)のマッピング — 分電盤の各ブレーカー表示をユーザーが確認する必要あり
- 分電盤メータリングの係数・単位の正確な解釈（EPC 0xD3=001226dd…, 0xC2=0x03 など実測値あり。ECHONET機器オブジェクト詳細規定と突き合わせて poll_hems.py 実装時に確定）
- 温度ロガーの有無・形式（実データ未入手）
- 常時稼働機をどうするか（RasPi新調 / 既存PCの常駐タスク）
