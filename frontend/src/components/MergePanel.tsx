import { useState } from "react";
import { FileInfo, mergeFiles } from "../api/client";

interface Props {
  files: FileInfo[];
  onClose: () => void;
  onMerged: () => void;
}

export default function MergePanel({ files, onClose, onMerged }: Props) {
  const [selectedOrder, setSelectedOrder] = useState<string[]>([]);
  const [outputFilename, setOutputFilename] = useState("merged.pdf");
  const [merging, setMerging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCheckbox = (filename: string, checked: boolean) => {
    if (checked) {
      setSelectedOrder((prev) => [...prev, filename]);
    } else {
      setSelectedOrder((prev) => prev.filter((f) => f !== filename));
    }
  };

  const handleMerge = async () => {
    if (selectedOrder.length < 2) {
      setError("2件以上のファイルを選択してください");
      return;
    }
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
      await mergeFiles(selectedOrder, outputFilename.trim());
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
          <label>結合するファイルを選択（チェックした順に結合）</label>
          {files.length === 0 ? (
            <p className="status-msg">ファイルがありません</p>
          ) : (
            <ul className="merge-file-list">
              {files.map((f) => (
                <li key={f.filename} className="merge-file-item">
                  <label className="merge-file-label">
                    <input
                      type="checkbox"
                      checked={selectedOrder.includes(f.filename)}
                      onChange={(e) => handleCheckbox(f.filename, e.target.checked)}
                    />
                    <span>{f.filename}</span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          {selectedOrder.length > 0 && (
            <p className="status-msg merge-order-hint">
              結合順: {selectedOrder.join(" → ")}
            </p>
          )}
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
            disabled={merging || selectedOrder.length < 2}
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
