class VideoEditorError(Exception):
    """基底例外"""


class VideoLoadError(VideoEditorError):
    """動画ファイルの読み込み失敗"""


class ReferenceFrameError(VideoEditorError):
    """基準フレーム番号が範囲外、または未設定"""


class CycleDetectionError(VideoEditorError):
    """サイクルが1つも検出できなかった"""


class SegmentExtractionError(VideoEditorError):
    """切り出し区間の処理失敗"""


class OverlayError(VideoEditorError):
    """ナンバリング合成の失敗"""


class ConcatError(VideoEditorError):
    """動画結合の失敗"""
