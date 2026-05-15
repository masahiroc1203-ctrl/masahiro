import { useState } from "react";
import { executeRename } from "../api/client";
import { buildFilename } from "../utils/rename";

interface Props {
  filename: string;
  onClose: () => void;
  onRenamed: () => void;
}

export default function RenamePanel({ filename, onClose, onRenamed }: Props) {
  const [kw1, setKw1] = useState("");
  const [kw2, setKw2] = useState("");
  const [kw3, setKw3] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);

  const preview = buildFilename(kw1, kw2, kw3);

  const handleRename = async () => {
    if (!preview) {
      setError("少なくとも1つキーワードを入力してください");
      return;
    }
    setRenaming(true);
    setError(null);
    try {
      await executeRename(filename, preview);
      onRenamed();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "リネームに失敗しました");
    } finally {
      setRenaming(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>ファイルのリネーム</h2>

        <div className="modal-field">
          <label>現在のファイル名</label>
          <p className="current-filename">{filename}</p>
        </div>

        <div className="modal-field keyword-grid">
          <label>キーワード 1</label>
          <input
            type="text"
            value={kw1}
            onChange={(e) => setKw1(e.target.value)}
            className="filename-input"
            placeholder="キーワード1"
          />
          <label>キーワード 2</label>
          <input
            type="text"
            value={kw2}
            onChange={(e) => setKw2(e.target.value)}
            className="filename-input"
            placeholder="キーワード2（省略可）"
          />
          <label>キーワード 3</label>
          <input
            type="text"
            value={kw3}
            onChange={(e) => setKw3(e.target.value)}
            className="filename-input"
            placeholder="キーワード3（省略可）"
          />
        </div>

        <div className="modal-field">
          <label>新しいファイル名（プレビュー）</label>
          <p className="hinmei-value">{preview || "—"}</p>
        </div>

        {error && <p className="status-msg error">{error}</p>}

        <div className="modal-actions">
          <button
            className="btn btn-primary"
            onClick={handleRename}
            disabled={renaming || !preview}
          >
            {renaming ? "実行中..." : "リネーム実行"}
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            キャンセル
          </button>
        </div>
      </div>
    </div>
  );
}
