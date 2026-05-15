# 詳細設計: CLI・設定ファイル

## CLI コマンド体系

```
video-editor <COMMAND> [OPTIONS]

コマンド:
  run        動画を処理してファイルを出力する（メイン）
  preview    サイクル検出結果のみ確認する（処理は行わない）
  inspect    動画の情報を表示する（FPS・解像度・長さ）
```

---

## `run` コマンド

```
Usage: video-editor run [OPTIONS] INPUT OUTPUT

Arguments:
  INPUT   入力動画ファイルパス
  OUTPUT  出力動画ファイルパス

Options:
  --config PATH            設定YAMLファイル（他オプションより優先度低）
  --ref-frame INT          基準フレーム番号 [必須: --config か --ref-frame のいずれか]
  --start FLOAT            切り出し開始オフセット（秒）  [default: 0.0]
  --end FLOAT              切り出し終了オフセット（秒）  [必須]
  --threshold FLOAT        類似度閾値 0〜1              [default: 0.92]
  --min-cycle-frames INT   最小サイクル長（フレーム数） [default: 30]
  --method [histogram|orb|ssim|combined]  類似度計算方法 [default: histogram]
  --no-overlay             ナンバリングオーバーレイを無効化
  --overlay-text TEXT      オーバーレイテキストテンプレート [default: "Cycle {n}"]
  --overlay-pos [top-left|top-right|bottom-left|bottom-right] [default: top-left]
  --bitrate TEXT           出力ビットレート             [default: 5M]
  --debug                  デバッグ情報を出力（類似度グラフを保存）
  --dry-run                サイクル検出のみ実行して結果を表示
  --help                   ヘルプを表示
```

### 使用例

```bash
# 最小構成
video-editor run factory.mp4 output.mp4 --ref-frame 150 --start 2.0 --end 8.0

# 設定ファイル使用
video-editor run factory.mp4 output.mp4 --config config.yaml

# デバッグ付き（類似度グラフを debug/ に保存）
video-editor run factory.mp4 output.mp4 --ref-frame 150 --start 2 --end 8 --debug

# 検出のみ確認（ファイルを生成しない）
video-editor run factory.mp4 output.mp4 --ref-frame 150 --start 2 --end 8 --dry-run
```

---

## `preview` コマンド

```
Usage: video-editor preview [OPTIONS] INPUT

Arguments:
  INPUT   入力動画ファイルパス

Options:
  --ref-frame INT     基準フレーム番号 [必須]
  --threshold FLOAT   類似度閾値       [default: 0.92]
  --output PATH       グラフ出力先     [default: ./detection_preview.png]
  --help              ヘルプを表示
```

出力: 類似度グラフ PNG（縦軸: 類似度, 横軸: 時刻）+ 検出サイクル境界の垂直線

```
[INFO] 動画情報: 1920x1080 @ 30fps, 5分23秒 (9690フレーム)
[INFO] 基準フレーム: #150 (00:00:05.000)
[INFO] スキャン中... ████████████████████ 100% (9690フレーム)
[INFO] 検出サイクル: 12件
  Cycle 1:  00:00:05.1 〜 00:00:26.4  (21.3秒)
  Cycle 2:  00:00:26.4 〜 00:00:47.8  (21.4秒)
  ...
[INFO] グラフ保存: ./detection_preview.png
```

---

## `inspect` コマンド

```
Usage: video-editor inspect INPUT

Arguments:
  INPUT   入力動画ファイルパス
```

出力例:

```
ファイル : factory.mp4
解像度   : 1920 x 1080
FPS      : 30.0
総フレーム: 9690
再生時間  : 5分 23.0秒
コーデック: h264
ファイルサイズ: 1.23 GB
```

---

## 設定ファイル優先度

CLIオプションと設定ファイルが競合した場合:

```
高 ←─────────────────────── 低
CLI直接指定 > 設定ファイル > デフォルト値
```

### 設定ファイル読み込みフロー

```python
def load_config(
    config_path: Optional[Path],
    cli_overrides: Dict[str, Any],
) -> AppConfig:
    base = {}
    if config_path:
        with open(config_path) as f:
            base = yaml.safe_load(f)
    
    # CLIオプションで上書き
    deep_merge(base, cli_overrides)
    
    return AppConfig.model_validate(base)
```

---

## 標準出力フォーマット

### 通常実行時

```
[INFO] 入力: factory.mp4 (1920x1080, 30fps, 5分23秒)
[INFO] 基準フレーム: #150 (00:00:05.000)
[INFO] サイクル検出中... 完了 (12件検出)
[INFO] 区間切り出し中... [████████████████████] 12/12
[INFO] ナンバリング合成中... [████████████████████] 12/12
[INFO] 動画結合中...
[INFO] 出力: output.mp4 (4.56秒)
[INFO] 完了 処理時間: 23.4秒
```

### dry-run 時

```
[DRY-RUN] サイクル検出結果:
  Cycle 01: 00:00:05.1 〜 00:00:26.4  (21.3秒) → 切り出し: 00:00:07.1 〜 00:00:13.1
  Cycle 02: 00:00:26.4 〜 00:00:47.8  (21.4秒) → 切り出し: 00:00:28.4 〜 00:00:34.4
  Cycle 03: 00:00:47.8 〜 00:01:09.1  (21.3秒) → 切り出し: 00:00:49.8 〜 00:00:55.8
  ...
[DRY-RUN] 合計 12件のクリップ, 各6.0秒, 出力予定: 72.0秒
```

### エラー時

```
[ERROR] サイクルが検出できませんでした。
  類似度閾値 (0.92) が高すぎる可能性があります。
  --threshold 0.80 などで試してみてください。
  詳細は --debug オプションで類似度グラフを確認できます。
```

---

## ログファイル出力（--debug 時）

```
debug/
├── detection_preview.png    # 類似度グラフ
├── reference_frame.png      # 使用した基準フレーム
├── similarities.csv         # フレーム番号, 類似度
└── processing.log           # 詳細ログ
```

similarities.csv フォーマット:
```csv
frame,time_sec,similarity
0,0.000,0.123
5,0.167,0.134
10,0.333,0.289
...
150,5.000,1.000  # 基準フレーム自身
```
