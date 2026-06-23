import { useState } from "react";
import { FileInfo, mergeFiles } from "../api/client";

interface Props {
  filesToMerge: FileInfo[];
  onClose: () => void;
  onMerged: () => void;
}

export default function MergePanel({ filesToMerge, onClose, onMerged }: Props) {
  const [outputFilename, setOutputFilename] = useState("merged.pdf");
  const [merging, setMerging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleMerge = async () => {
    if (!outputFilename.trim()) {
      setError("出力ファイル名を入力してください");
      return;
    }
    if (!outputFilename.toLowerCase().endsWith(".pdf")) {
      setError("出力ファイル名は .pdf で終わる必要があります");
      return;
    }
    setMerging(true);
    setError(null);
    try {
      await mergeFiles(filesToMerge.map((f) => f.filename), outputFilename.trim());
      onMerged();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "結合に失敗しました");
    } finally {
      setMerging(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content merge-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <h2>PDFを結合</h2>

        <div className="modal-field">
          <label>結合するファイル（一覧の順番で結合）</label>
          <ol className="merge-file-list">
            {filesToMerge.map((f) => (
              <li key={f.filename} className="merge-file-item">{f.filename}</li>
            ))}
          </ol>
        </div>

        <div className="modal-field">
          <label htmlFor="output-filename">出力ファイル名</label>
          <input
            id="output-filename"
            type="text"
            value={outputFilename}
            onChange={(e) => setOutputFilename(e.target.value)}
            className="filename-input"
          />
        </div>

        {error && <p className="status-msg error">{error}</p>}

        <div className="modal-actions">
          <button
            className="btn btn-primary"
            onClick={handleMerge}
            disabled={merging}
          >
            {merging ? "結合中..." : "結合実行"}
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            キャンセル
          </button>
        </div>
      </div>
    </div>
  );
}
