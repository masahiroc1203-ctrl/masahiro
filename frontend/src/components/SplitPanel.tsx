import { useEffect, useState } from "react";
import { getContent, splitFile } from "../api/client";

interface Props {
  filename: string;
  onClose: () => void;
  onSplit: () => void;
}

type SplitMode = "ranges" | "every";

function parseRanges(input: string): [number, number][] | null {
  const parts = input.split(",").map((s) => s.trim()).filter(Boolean);
  const result: [number, number][] = [];
  for (const part of parts) {
    if (part.includes("-")) {
      const [startStr, endStr] = part.split("-").map((s) => s.trim());
      const start = parseInt(startStr, 10);
      const end = parseInt(endStr, 10);
      if (isNaN(start) || isNaN(end)) return null;
      result.push([start, end]);
    } else {
      const n = parseInt(part, 10);
      if (isNaN(n)) return null;
      result.push([n, n]);
    }
  }
  return result.length > 0 ? result : null;
}

export default function SplitPanel({ filename, onClose, onSplit }: Props) {
  const [totalPages, setTotalPages] = useState<number | null>(null);
  const [loadingPages, setLoadingPages] = useState(true);
  const [pageLoadError, setPageLoadError] = useState<string | null>(null);

  const [mode, setMode] = useState<SplitMode>("ranges");
  const [rangesInput, setRangesInput] = useState("");
  const [everyInput, setEveryInput] = useState("1");

  const [splitting, setSplitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoadingPages(true);
    setPageLoadError(null);
    getContent(filename)
      .then((result) => setTotalPages(result.total_pages))
      .catch((e) => setPageLoadError(e instanceof Error ? e.message : "ページ数の取得に失敗しました"))
      .finally(() => setLoadingPages(false));
  }, [filename]);

  const handleSplit = async () => {
    setError(null);

    if (mode === "ranges") {
      const ranges = parseRanges(rangesInput);
      if (!ranges) {
        setError("ページ範囲の形式が正しくありません（例: 1-3, 4-6, 7）");
        return;
      }
      setSplitting(true);
      try {
        await splitFile(filename, "ranges", ranges, undefined);
        onSplit();
        onClose();
      } catch (e) {
        setError(e instanceof Error ? e.message : "分割に失敗しました");
      } finally {
        setSplitting(false);
      }
    } else {
      const every = parseInt(everyInput, 10);
      if (isNaN(every) || every < 1) {
        setError("Nは1以上の整数を入力してください");
        return;
      }
      setSplitting(true);
      try {
        await splitFile(filename, "every", undefined, every);
        onSplit();
        onClose();
      } catch (e) {
        setError(e instanceof Error ? e.message : "分割に失敗しました");
      } finally {
        setSplitting(false);
      }
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content split-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <h2>PDFを分割</h2>

        <div className="modal-field">
          <label>ファイル名</label>
          <p className="current-filename">{filename}</p>
        </div>

        <div className="modal-field">
          <label>総ページ数</label>
          {loadingPages ? (
            <p className="status-msg">読み込み中...</p>
          ) : pageLoadError ? (
            <p className="status-msg error">{pageLoadError}</p>
          ) : (
            <p className="current-filename">{totalPages} ページ</p>
          )}
        </div>

        <div className="modal-field">
          <label>分割モード</label>
          <div className="split-mode-options">
            <label className="split-radio-label">
              <input
                type="radio"
                name="split-mode"
                value="ranges"
                checked={mode === "ranges"}
                onChange={() => setMode("ranges")}
              />
              ページ範囲指定
            </label>
            <label className="split-radio-label">
              <input
                type="radio"
                name="split-mode"
                value="every"
                checked={mode === "every"}
                onChange={() => setMode("every")}
              />
              Nページごとに分割
            </label>
          </div>
        </div>

        {mode === "ranges" ? (
          <div className="modal-field">
            <label htmlFor="ranges-input">ページ範囲（カンマ区切り、例: 1-3, 4-6, 7）</label>
            <textarea
              id="ranges-input"
              value={rangesInput}
              onChange={(e) => setRangesInput(e.target.value)}
              className="filename-input split-ranges-input"
              placeholder="例: 1-3, 4-6, 7"
              rows={3}
            />
          </div>
        ) : (
          <div className="modal-field">
            <label htmlFor="every-input">Nページごとに分割</label>
            <input
              id="every-input"
              type="number"
              min={1}
              value={everyInput}
              onChange={(e) => setEveryInput(e.target.value)}
              className="filename-input split-every-input"
            />
          </div>
        )}

        {error && <p className="status-msg error">{error}</p>}

        <div className="modal-actions">
          <button
            className="btn btn-primary"
            onClick={handleSplit}
            disabled={splitting || loadingPages}
          >
            {splitting ? "分割中..." : "分割実行"}
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            キャンセル
          </button>
        </div>
      </div>
    </div>
  );
}
