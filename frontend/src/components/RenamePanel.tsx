import { useEffect, useState } from "react";
import { previewRename, executeRename } from "../api/client";

interface Props {
  filename: string;
  onClose: () => void;
  onRenamed: () => void;
}

export default function RenamePanel({ filename, onClose, onRenamed }: Props) {
  const [loading, setLoading] = useState(true);
  const [hinmei, setHinmei] = useState<string | null>(null);
  const [newFilename, setNewFilename] = useState(filename);
  const [error, setError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    previewRename(filename)
      .then((result) => {
        setHinmei(result.hinmei);
        setNewFilename(result.suggested_filename ?? filename);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "解析に失敗しました");
        setNewFilename(filename);
      })
      .finally(() => setLoading(false));
  }, [filename]);

  const handleRename = async () => {
    if (!newFilename.trim()) {
      setError("ファイル名を入力してください");
      return;
    }
    if (!newFilename.toLowerCase().endsWith(".pdf")) {
      setError("ファイル名は .pdf で終わる必要があります");
      return;
    }
    setRenaming(true);
    setError(null);
    try {
      await executeRename(filename, newFilename.trim());
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

        {loading ? (
          <p className="status-msg">品名を解析中...</p>
        ) : (
          <>
            {hinmei !== null ? (
              <div className="modal-field">
                <label>抽出された品名</label>
                <p className="hinmei-value">{hinmei}</p>
              </div>
            ) : (
              !error && (
                <p className="status-msg warning">
                  品名が見つかりませんでした。ファイル名を手動で入力してください。
                </p>
              )
            )}

            <div className="modal-field">
              <label htmlFor="new-filename">新しいファイル名</label>
              <input
                id="new-filename"
                type="text"
                value={newFilename}
                onChange={(e) => setNewFilename(e.target.value)}
                className="filename-input"
              />
            </div>

            {error && <p className="status-msg error">{error}</p>}

            <div className="modal-actions">
              <button
                className="btn btn-primary"
                onClick={handleRename}
                disabled={renaming}
              >
                {renaming ? "実行中..." : "リネーム実行"}
              </button>
              <button className="btn btn-secondary" onClick={onClose}>
                キャンセル
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
