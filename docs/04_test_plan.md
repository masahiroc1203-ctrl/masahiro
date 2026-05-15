# 詳細設計: テスト計画

## テスト戦略

```
ユニットテスト  ─ 各モジュールを独立してテスト（モック使用）
統合テスト     ─ パイプライン全体をテスト動画で検証
E2Eテスト      ─ CLIコマンドを実際に実行して出力を確認
```

---

## テスト用動画の作成（フィクスチャ）

実際の工場動画がなくてもテストできるよう、OpenCV でテスト動画を生成する。

```python
# tests/fixtures/create_test_video.py

def create_cyclic_video(
    output_path: str,
    cycle_count: int = 5,
    cycle_length_sec: float = 3.0,
    fps: int = 30,
    resolution: Tuple[int, int] = (640, 480),
) -> None:
    """
    サイクリックなテスト動画を生成する。
    各サイクルの最初のフレームに固定の白い四角を描画し、
    それ以外は徐々に変化するグラデーション。
    → 白い四角のフレームが「ホーム位置」の基準フレームに相当。
    """
    writer = cv2.VideoWriter(output_path, ...)
    for cycle in range(cycle_count):
        for frame_in_cycle in range(int(cycle_length_sec * fps)):
            img = np.zeros((height, width, 3), dtype=np.uint8)
            if frame_in_cycle == 0:
                # 基準フレーム: 白い四角
                cv2.rectangle(img, (50, 50), (200, 200), (255, 255, 255), -1)
            else:
                # 通常フレーム: 変化するグラデーション
                t = frame_in_cycle / (cycle_length_sec * fps)
                img[:, :, 0] = int(255 * t)  # Bチャンネルが徐々に増加
            writer.write(img)
    writer.release()
```

---

## ユニットテスト

### test_loader.py

```python
class TestVideoLoader:
    def test_load_valid_video(self, test_video_path):
        """有効な動画を読み込めること"""
        loader = VideoLoader()
        info = loader.load(test_video_path)
        assert info.fps == 30.0
        assert info.total_frames > 0

    def test_load_nonexistent_file(self):
        """存在しないファイルで VideoLoadError を送出すること"""
        with pytest.raises(VideoLoadError):
            VideoLoader().load("nonexistent.mp4")

    def test_get_frame_in_range(self, loaded_video):
        """指定フレームが正しい形状で返ること"""
        loader, info = loaded_video
        frame = loader.get_frame(0)
        assert frame.shape == (info.height, info.width, 3)

    def test_get_frame_out_of_range(self, loaded_video):
        """範囲外フレーム番号で IndexError を送出すること"""
        loader, info = loaded_video
        with pytest.raises(IndexError):
            loader.get_frame(info.total_frames + 1)

    def test_iter_frames_stride(self, loaded_video):
        """stride が正しく動作すること"""
        loader, info = loaded_video
        frames = list(loader.iter_frames(0, 30, stride=5))
        assert len(frames) == 6  # 0, 5, 10, 15, 20, 25

    def test_context_manager(self, test_video_path):
        """コンテキストマネージャで正しく解放されること"""
        with VideoLoader() as loader:
            loader.load(test_video_path)
        # 解放後のアクセスでエラーになること
        with pytest.raises(Exception):
            loader.get_frame(0)
```

### test_cycle_detector.py

```python
class TestCycleDetector:
    @pytest.fixture
    def cyclic_video(self, tmp_path):
        """5サイクル, 各3秒, 30fps のテスト動画"""
        path = tmp_path / "cyclic.mp4"
        create_cyclic_video(str(path), cycle_count=5, cycle_length_sec=3.0)
        return path

    def test_compute_similarity_same_frame(self, detector, reference_frame):
        """同一フレームとの類似度は 1.0 に近いこと"""
        detector.set_reference_frame(reference_frame)
        sim = detector.compute_similarity(reference_frame)
        assert sim > 0.99

    def test_compute_similarity_different_frame(self, detector, reference_frame, other_frame):
        """異なるフレームとの類似度は低いこと"""
        detector.set_reference_frame(reference_frame)
        sim = detector.compute_similarity(other_frame)
        assert sim < 0.5

    def test_detect_correct_cycle_count(self, cyclic_video):
        """5サイクルの動画から5件検出できること"""
        loader = VideoLoader()
        video = loader.load(str(cyclic_video))
        reference = loader.get_frame(0)  # 0フレーム目が基準

        detector = CycleDetector(CycleConfig(similarity_threshold=0.90))
        detector.set_reference_frame(reference)
        boundaries = detector.detect_cycles(loader, video)

        assert len(boundaries) == 5

    def test_cycle_ids_are_sequential(self, boundaries):
        """サイクルIDが1から連番であること"""
        ids = [b.cycle_id for b in boundaries]
        assert ids == list(range(1, len(ids) + 1))

    def test_no_cycle_raises_error(self, loaded_uniform_video):
        """サイクルが検出できない場合 CycleDetectionError を送出すること"""
        loader, video = loaded_uniform_video
        detector = CycleDetector(CycleConfig(similarity_threshold=0.99))
        detector.set_reference_frame(loader.get_frame(0))
        with pytest.raises(CycleDetectionError):
            detector.detect_cycles(loader, video)

    def test_min_cycle_frames_filter(self, loader, video, detector):
        """min_cycle_frames 未満のピークが除外されること"""
        # threshold を下げて大量のピークが出る状態を作り、
        # min_cycle_frames で正しくフィルタされることを確認
        ...
```

### test_extractor.py

```python
class TestSegmentExtractor:
    def test_extract_creates_file(self, boundary, video_info, tmp_path):
        """切り出しファイルが生成されること"""
        config = ExtractionConfig(start_offset_sec=0.5, end_offset_sec=2.0)
        extractor = SegmentExtractor(config, OutputConfig(video_path=tmp_path/"out.mp4", temp_dir=tmp_path))
        segment = extractor.extract(boundary, video_info)
        assert Path(segment.clip_path).exists()

    def test_extract_duration(self, boundary, video_info, tmp_path):
        """切り出しクリップの長さが設定通りであること（±0.1秒の誤差許容）"""
        start, end = 0.5, 2.0
        segment = extractor.extract(boundary, video_info)
        actual_duration = get_video_duration(segment.clip_path)
        assert abs(actual_duration - (end - start)) < 0.1

    def test_validate_offset_exceeds_cycle(self, short_boundary, video_info):
        """オフセットがサイクル長を超える場合 validate が False を返すこと"""
        config = ExtractionConfig(start_offset_sec=0.0, end_offset_sec=100.0)
        extractor = SegmentExtractor(config, ...)
        assert not extractor.validate(short_boundary, video_info)

    def test_extract_all_skips_invalid(self, boundaries_with_short_one, video_info):
        """無効なサイクルがスキップされ、有効なものだけが返ること"""
        segments = extractor.extract_all(boundaries_with_short_one, video_info)
        assert len(segments) < len(boundaries_with_short_one)
```

### test_overlay.py

```python
class TestNumberingOverlay:
    def test_text_rendered_on_frame(self):
        """フレームにテキストが描画されること"""
        config = OverlayConfig(enabled=True, text_template="Cycle {n}")
        overlay = NumberingOverlay(config)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = overlay._render_text(frame, "Cycle 1")
        # 元フレームと異なること（テキストが描画されている）
        assert not np.array_equal(frame, result)

    def test_text_template_formatting(self):
        """テンプレート変数が正しく展開されること"""
        ...

    def test_overlay_disabled(self, segment):
        """enabled=False のとき元ファイルパスのまま返ること"""
        config = OverlayConfig(enabled=False)
        overlay = NumberingOverlay(config)
        result = overlay.apply_to_clip(segment)
        assert result.clip_path == segment.clip_path
```

### test_concat.py

```python
class TestVideoConcat:
    def test_concat_output_exists(self, segments, tmp_path):
        """結合ファイルが生成されること"""
        concat = VideoConcat(OutputConfig(video_path=tmp_path/"out.mp4", ...))
        result = concat.concat(segments, tmp_path/"out.mp4")
        assert result.exists()

    def test_concat_duration(self, segments, tmp_path):
        """出力動画の長さが各クリップの合計であること"""
        expected = sum(get_video_duration(s.clip_path) for s in segments)
        result_path = concat.concat(segments, tmp_path/"out.mp4")
        actual = get_video_duration(str(result_path))
        assert abs(actual - expected) < 0.5  # 0.5秒以内の誤差

    def test_cleanup_removes_temp_files(self, segments):
        """cleanup_temp で一時ファイルが削除されること"""
        concat.cleanup_temp(segments)
        for s in segments:
            assert not Path(s.clip_path).exists()
```

---

## 統合テスト

```python
class TestPipelineIntegration:
    def test_end_to_end(self, cyclic_video, tmp_path):
        """
        5サイクルのテスト動画で全パイプラインを実行し、
        出力ファイルが生成され、内容が正しいことを確認。
        """
        config = AppConfig(
            input=InputConfig(video_path=cyclic_video, reference_frame=0),
            cycle=CycleConfig(similarity_threshold=0.90),
            extraction=ExtractionConfig(start_offset_sec=0.5, end_offset_sec=2.0),
            overlay=OverlayConfig(enabled=True),
            output=OutputConfig(video_path=tmp_path/"out.mp4", temp_dir=tmp_path/"tmp"),
        )
        pipeline = VideoEditingPipeline(config)
        result = pipeline.run()

        assert result.detected_cycles == 5
        assert result.extracted_segments == 5
        assert Path(result.output_path).exists()
        # 5クリップ × 1.5秒 = 7.5秒の動画が出力されること
        assert abs(get_video_duration(result.output_path) - 7.5) < 0.5
```

---

## E2Eテスト（CLIテスト）

```python
from typer.testing import CliRunner
from src.cli import app

class TestCLI:
    def test_run_command(self, cyclic_video, tmp_path):
        runner = CliRunner()
        result = runner.invoke(app, [
            "run", str(cyclic_video), str(tmp_path/"out.mp4"),
            "--ref-frame", "0",
            "--start", "0.5",
            "--end", "2.0",
        ])
        assert result.exit_code == 0
        assert (tmp_path / "out.mp4").exists()

    def test_dry_run_no_output_file(self, cyclic_video, tmp_path):
        runner = CliRunner()
        result = runner.invoke(app, [
            "run", str(cyclic_video), str(tmp_path/"out.mp4"),
            "--ref-frame", "0", "--start", "0.5", "--end", "2.0",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert not (tmp_path / "out.mp4").exists()
        assert "Cycle" in result.output

    def test_inspect_command(self, cyclic_video):
        runner = CliRunner()
        result = runner.invoke(app, ["inspect", str(cyclic_video)])
        assert result.exit_code == 0
        assert "FPS" in result.output
```

---

## テストカバレッジ目標

| モジュール | 目標カバレッジ |
|-----------|--------------|
| loader.py | 90% |
| cycle_detector.py | 85% |
| extractor.py | 90% |
| overlay.py | 80% |
| concat.py | 85% |
| pipeline.py | 80% |
| cli.py | 75% |

---

## CI 設定（GitHub Actions）

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install FFmpeg
        run: sudo apt-get install -y ffmpeg
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run tests
        run: pytest tests/ --cov=src --cov-report=xml -v
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```
