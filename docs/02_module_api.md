# 詳細設計: モジュール API

## モジュール依存関係

```
cli.py
  └── pipeline.py         ← 全体オーケストレーション
        ├── loader.py
        ├── cycle_detector.py
        ├── extractor.py
        ├── overlay.py
        └── concat.py

config.py                 ← 全モジュールから参照（依存注入）
exceptions.py             ← 全モジュールから参照
```

---

## VideoLoader (`loader.py`)

```python
class VideoLoader:
    def load(self, path: str | Path) -> VideoInfo:
        """
        動画ファイルを開き VideoInfo を返す。
        失敗時は VideoLoadError を送出。
        内部では VideoCapture を保持し、以降の get_frame / iter_frames で再利用。
        """

    def get_frame(self, frame_num: int) -> np.ndarray:
        """
        指定フレーム番号の画像（BGR uint8）を返す。
        範囲外の場合は IndexError。
        """

    def iter_frames(
        self,
        start: int,
        end: int,
        stride: int = 1,
    ) -> Iterator[Tuple[int, np.ndarray]]:
        """
        [start, end) の範囲を stride おきにフレームを yield する。
        Tuple[フレーム番号, 画像] を返す。
        """

    def release(self) -> None:
        """VideoCapture を解放する。コンテキストマネージャでも使用可。"""

    def __enter__(self) -> "VideoLoader": ...
    def __exit__(self, *args) -> None: ...
```

### 内部実装ノート
- `cv2.VideoCapture` の `set(CAP_PROP_POS_FRAMES, n)` でランダムアクセス
- FPS は `cap.get(CAP_PROP_FPS)` で取得。0 が返る場合は FFprobe でフォールバック
- コーデック判定は `ffprobe -v error -select_streams v:0 -show_entries stream=codec_name`

---

## CycleDetector (`cycle_detector.py`)

```python
class CycleDetector:
    def __init__(self, config: CycleConfig):
        self._config = config
        self._reference: Optional[np.ndarray] = None

    def set_reference_frame(self, frame: np.ndarray) -> None:
        """基準フレームをセットし、内部表現（ヒストグラム等）を事前計算する。"""

    def compute_similarity(self, frame: np.ndarray) -> float:
        """
        基準フレームとの類似度を [0, 1] で返す。
        set_reference_frame 未呼び出しの場合は ReferenceFrameError。
        """

    def scan(
        self,
        loader: VideoLoader,
        video: VideoInfo,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[float]:
        """
        動画全体をスキャンし、各フレームの類似度リストを返す。
        scan_stride おきにサンプリングし、インデックスは実フレーム番号に対応。
        """

    def detect_peaks(self, similarities: List[float]) -> List[int]:
        """
        類似度リストからピーク（サイクル開始点）のフレーム番号リストを返す。
        scipy.signal.find_peaks を使用。
        """

    def detect_cycles(
        self,
        loader: VideoLoader,
        video: VideoInfo,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[CycleBoundary]:
        """
        scan → detect_peaks → refine → build_boundaries の一連処理。
        サイクルが1つも検出できない場合は CycleDetectionError。
        """

    def visualize(
        self,
        similarities: List[float],
        boundaries: List[CycleBoundary],
        output_path: str,
    ) -> None:
        """類似度グラフと検出境界を PNG で保存する（デバッグ用）。"""
```

### サイクル検出アルゴリズム詳細

```
Step 1: 基準フレームの前処理
  - リサイズ (256x256) して計算コスト削減
  - HSV変換してヒストグラム算出 (H:50bins, S:60bins, V:なし)
  - L2正規化

Step 2: スキャン（stride=5 デフォルト）
  for i in range(0, total_frames, stride):
    frame = loader.get_frame(i)
    sim[i] = compute_similarity(frame)
    strideの間は線形補間で埋める（任意）

Step 3: ピーク検出
  peaks, _ = scipy.signal.find_peaks(
    sim,
    height=threshold,          # 閾値以上のピークのみ
    distance=min_cycle_frames, # 最小サイクル長（近すぎるピークを除外）
  )

Step 4: ピーク精細化
  for peak in peaks:
    window = sim[peak-refine_window : peak+refine_window]
    refined = peak - refine_window + argmax(window)

Step 5: CycleBoundary 構築
  for i, start_frame in enumerate(refined_peaks):
    end_frame = refined_peaks[i+1] - 1 if i+1 < len else total_frames - 1
    yield CycleBoundary(
      cycle_id = i + 1,
      start_frame = start_frame,
      end_frame = end_frame,
      ...
    )
```

### 類似度計算メソッド比較

| メソッド | 速度 | 精度 | 照明変化への強さ | 備考 |
|---------|------|------|----------------|------|
| histogram | ★★★ | ★★ | ★★★ | デフォルト推奨 |
| orb | ★★ | ★★★ | ★★ | 部分一致に強い |
| ssim | ★ | ★★★ | ★ | 重い、小差検出向き |
| combined | ★★ | ★★★ | ★★★ | histogram×0.6 + orb×0.4 |

---

## SegmentExtractor (`extractor.py`)

```python
class SegmentExtractor:
    def __init__(self, config: ExtractionConfig, output_config: OutputConfig):
        self._config = config
        self._output_config = output_config

    def validate(self, boundary: CycleBoundary, video: VideoInfo) -> bool:
        """
        オフセット指定がサイクル長に収まるか確認。
        収まらない場合は警告ログを出して False を返す（例外は出さない）。
        """

    def extract(
        self,
        boundary: CycleBoundary,
        video: VideoInfo,
    ) -> Segment:
        """
        1サイクル分の区間を一時ファイルに切り出す。
        FFmpeg の -ss / -to オプションで精度切り出し。
        """

    def extract_all(
        self,
        boundaries: List[CycleBoundary],
        video: VideoInfo,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[Segment]:
        """
        全サイクルを一括処理。validate で NG のサイクルはスキップ。
        """
```

### FFmpeg 切り出しコマンド

```bash
ffmpeg \
  -ss {start_sec}          \  # 入力シーク（-ss を入力前に置くと高速だが不精確）
  -i {input_path}          \
  -to {duration_sec}       \  # -ss からの長さ
  -c:v libx264             \
  -b:v {bitrate}           \
  -an                      \  # 音声なし（設定による）
  -y {output_clip_path}
```

**注意**: 精度を優先する場合は `-ss` を入力後に置く（`-i` の後）。ただし低速になる。  
工場動画はキーフレーム間隔が長い場合があるため、精度モードを推奨。

```bash
# 精度優先モード
ffmpeg -i {input} -ss {start} -to {end} -c:v libx264 -y {output}

# 速度優先モード（先頭付近のIフレームからデコード）
ffmpeg -ss {start} -i {input} -t {duration} -c:v libx264 -y {output}
```

---

## NumberingOverlay (`overlay.py`)

```python
class NumberingOverlay:
    def __init__(self, config: OverlayConfig):
        self._config = config

    def _render_text(
        self,
        frame: np.ndarray,
        text: str,
    ) -> np.ndarray:
        """
        フレームにテキストを描画して返す（元フレームは変更しない）。
        背景矩形 → テキスト の順で描画。
        """

    def apply_to_clip(self, segment: Segment) -> Segment:
        """
        クリップの全フレームにオーバーレイを描画し、新しい一時ファイルとして保存。
        元の Segment を更新した新 Segment を返す。
        """

    def apply_all(
        self,
        segments: List[Segment],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[Segment]:
        """全セグメントに一括適用。"""
```

### テキスト位置計算

```python
POSITIONS = {
    "top-left":     lambda w, h, tw, th, m: (m, m + th),
    "top-right":    lambda w, h, tw, th, m: (w - tw - m, m + th),
    "bottom-left":  lambda w, h, tw, th, m: (m, h - m),
    "bottom-right": lambda w, h, tw, th, m: (w - tw - m, h - m),
}
# w,h = フレームサイズ, tw,th = テキスト描画サイズ, m = margin_px
```

### テキストテンプレート変数

| 変数 | 内容 | 例 |
|------|------|-----|
| `{n}` | サイクル番号（1始まり） | `1`, `2`, ... |
| `{n:03d}` | ゼロ埋め番号 | `001`, `002`, ... |
| `{t}` | 元動画の開始タイムスタンプ | `00:01:23.456` |

---

## VideoConcat (`concat.py`)

```python
class VideoConcat:
    def __init__(self, config: OutputConfig):
        self._config = config

    def concat(
        self,
        segments: List[Segment],
        output_path: str | Path,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Path:
        """
        全クリップを順番に結合し、output_path に書き出す。
        内部的に FFmpeg の concat demuxer を使用。
        """

    def _write_concat_list(self, segments: List[Segment], list_path: Path) -> None:
        """
        FFmpeg concat demuxer 用の一覧ファイルを書き出す。

        file '/tmp/clip_001.mp4'
        file '/tmp/clip_002.mp4'
        ...
        """

    def cleanup_temp(self, segments: List[Segment]) -> None:
        """一時クリップファイルを削除する。"""
```

### FFmpeg concat コマンド

```bash
ffmpeg \
  -f concat          \
  -safe 0            \
  -i {concat_list}   \
  -c copy            \  # 再エンコードなし（同一コーデックの場合）
  -y {output_path}
```

**注意**: クリップ間でコーデック・解像度・FPS が異なる場合は `-c copy` が使えない。  
そのため SegmentExtractor で出力コーデックを統一し、concat 時は `-c copy` を使う設計とする。

---

## Pipeline (`pipeline.py`)

```python
class VideoEditingPipeline:
    def __init__(self, config: AppConfig):
        self._config = config
        self._loader = VideoLoader()
        self._detector = CycleDetector(config.cycle)
        self._extractor = SegmentExtractor(config.extraction, config.output)
        self._overlay = NumberingOverlay(config.overlay)
        self._concat = VideoConcat(config.output)

    def run(
        self,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> ProcessingResult:
        """
        パイプライン全体を実行する。
        progress_callback(stage_name, 0.0~1.0) で進捗を通知。
        """

    def preview_detection(self, output_path: str) -> None:
        """
        サイクル検出結果のみを実行し、類似度グラフを PNG で保存。
        本処理前の確認用。
        """
```

### run() の内部フロー

```
1. temp_dir 作成
2. loader.load(input_path)                    → VideoInfo
3. detector.set_reference_frame(frame[ref])
4. detector.detect_cycles(loader, video)      → List[CycleBoundary]
   ※ サイクル0件なら CycleDetectionError
5. extractor.extract_all(boundaries, video)   → List[Segment]
6. overlay.apply_all(segments)                → List[Segment]  (enabled時のみ)
7. concat.concat(segments, output_path)       → Path
8. concat.cleanup_temp(segments)
9. return ProcessingResult
```
