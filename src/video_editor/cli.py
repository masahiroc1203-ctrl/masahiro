from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import typer

from .config import load_config
from .exceptions import VideoEditorError
from .loader import VideoLoader
from .pipeline import VideoEditingPipeline

app = typer.Typer(
    name="video-editor",
    help="工場工程動画 サイクル自動編集ツール",
    no_args_is_help=True,
)


@app.command("run")
def run_cmd(
    input_video: Path = typer.Argument(..., metavar="INPUT", help="入力動画ファイルパス"),
    output_video: Path = typer.Argument(..., metavar="OUTPUT", help="出力動画ファイルパス"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="設定YAMLファイル"),
    ref_frame: Optional[int] = typer.Option(None, "--ref-frame", help="基準フレーム番号"),
    start: Optional[float] = typer.Option(None, "--start", help="切り出し開始オフセット（秒）"),
    end: Optional[float] = typer.Option(None, "--end", help="切り出し終了オフセット（秒）"),
    threshold: Optional[float] = typer.Option(None, "--threshold", help="類似度閾値 [0-1]"),
    no_overlay: bool = typer.Option(False, "--no-overlay", help="ナンバリングオーバーレイを無効化"),
    dry_run: bool = typer.Option(False, "--dry-run", help="サイクル検出のみ実行（ファイル出力なし）"),
    debug: bool = typer.Option(False, "--debug", help="デバッグ情報を出力"),
) -> None:
    """動画を処理してサイクル切り出し結合ファイルを出力する。"""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    overrides: dict = {
        "input": {"video_path": str(input_video)},
        "output": {"video_path": str(output_video)},
    }
    if ref_frame is not None:
        overrides["input"]["reference_frame"] = ref_frame
    if start is not None:
        overrides.setdefault("extraction", {})["start_offset_sec"] = start
    if end is not None:
        overrides.setdefault("extraction", {})["end_offset_sec"] = end
    if threshold is not None:
        overrides.setdefault("cycle", {})["similarity_threshold"] = threshold
    if no_overlay:
        overrides["overlay"] = {"enabled": False}

    try:
        cfg = load_config(config, overrides)
    except Exception as e:
        typer.echo(f"[ERROR] 設定エラー: {e}", err=True)
        raise typer.Exit(1)

    pipeline = VideoEditingPipeline(cfg)

    if dry_run:
        typer.echo("[DRY-RUN] サイクル検出結果:")
        try:
            boundaries = pipeline.preview_detection("/dev/null")
            extract_dur = cfg.extraction.end_offset_sec - cfg.extraction.start_offset_sec
            for b in boundaries:
                cut_s = b.start_sec + cfg.extraction.start_offset_sec
                cut_e = b.start_sec + cfg.extraction.end_offset_sec
                typer.echo(
                    f"  Cycle {b.cycle_id:02d}: "
                    f"{_fmt(b.start_sec)} 〜 {_fmt(b.end_sec)}  "
                    f"→ 切り出し: {_fmt(cut_s)} 〜 {_fmt(cut_e)}"
                )
            total_sec = len(boundaries) * extract_dur
            typer.echo(
                f"[DRY-RUN] 合計 {len(boundaries)} クリップ, "
                f"各 {extract_dur:.1f}秒, 出力予定: {total_sec:.1f}秒"
            )
        except VideoEditorError as e:
            typer.echo(f"[ERROR] {e}", err=True)
            raise typer.Exit(1)
        return

    def progress(stage: str, pct: float) -> None:
        bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
        typer.echo(f"\r[INFO] {stage:<16} [{bar}] {int(pct*100):3d}%", nl=False)

    try:
        result = pipeline.run(progress_callback=progress)
        typer.echo()
        typer.echo(
            f"[INFO] 完了: {result.extracted_segments} クリップ → {result.output_path}"
        )
        typer.echo(f"[INFO] 処理時間: {result.processing_time_sec:.1f}秒")
        if result.skipped_cycles:
            typer.echo(f"[WARN] スキップ: Cycle {result.skipped_cycles}", err=True)
    except VideoEditorError as e:
        typer.echo(f"\n[ERROR] {e}", err=True)
        raise typer.Exit(1)


@app.command("preview")
def preview_cmd(
    input_video: Path = typer.Argument(..., metavar="INPUT", help="入力動画ファイルパス"),
    ref_frame: int = typer.Option(..., "--ref-frame", help="基準フレーム番号"),
    threshold: float = typer.Option(0.92, "--threshold", help="類似度閾値"),
    output: Path = typer.Option(
        Path("detection_preview.png"), "--output", "-o", help="グラフ出力先PNG"
    ),
) -> None:
    """サイクル検出結果のみ確認する（ファイルは出力しない）。"""
    overrides = {
        "input": {"video_path": str(input_video), "reference_frame": ref_frame},
        "cycle": {"similarity_threshold": threshold},
        "extraction": {"start_offset_sec": 0.0, "end_offset_sec": 1.0},
        "output": {"video_path": "/dev/null"},
    }
    try:
        cfg = load_config(None, overrides)
        pipeline = VideoEditingPipeline(cfg)
        boundaries = pipeline.preview_detection(str(output))
        typer.echo(f"[INFO] 検出サイクル: {len(boundaries)} 件")
        for b in boundaries:
            typer.echo(
                f"  Cycle {b.cycle_id:02d}: "
                f"{_fmt(b.start_sec)} 〜 {_fmt(b.end_sec)} "
                f"({b.end_sec - b.start_sec:.1f}秒)"
            )
        typer.echo(f"[INFO] グラフ保存: {output}")
    except VideoEditorError as e:
        typer.echo(f"[ERROR] {e}", err=True)
        raise typer.Exit(1)


@app.command("inspect")
def inspect_cmd(
    input_video: Path = typer.Argument(..., metavar="INPUT", help="入力動画ファイルパス"),
) -> None:
    """動画の情報を表示する。"""
    with VideoLoader() as loader:
        try:
            info = loader.load(str(input_video))
        except VideoEditorError as e:
            typer.echo(f"[ERROR] {e}", err=True)
            raise typer.Exit(1)

    m, s = divmod(info.duration_sec, 60)
    typer.echo(f"ファイル    : {info.path}")
    typer.echo(f"解像度      : {info.width} x {info.height}")
    typer.echo(f"FPS         : {info.fps:.3f}")
    typer.echo(f"総フレーム数: {info.total_frames}")
    typer.echo(f"再生時間    : {int(m)}分 {s:.1f}秒")
    typer.echo(f"コーデック  : {info.codec}")


def _fmt(sec: float) -> str:
    m, s = divmod(sec, 60)
    return f"{int(m):02d}:{s:06.3f}"


if __name__ == "__main__":
    app()
