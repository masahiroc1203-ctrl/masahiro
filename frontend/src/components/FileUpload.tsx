import { useCallback, useState } from "react";
import { uploadFile, uploadFileAutoRename } from "../api/client";

interface Props {
  onUploadComplete: () => void;
}

interface UploadLog {
  filename: string;
  hinmei: string | null;
  renamed: boolean;
}

export default function FileUpload({ onUploadComplete }: Props) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [autoRename, setAutoRename] = useState(false);
  const [logs, setLogs] = useState<UploadLog[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      setError(null);
      setLogs([]);

      const pdfFiles = Array.from(files).filter((f) =>
        f.name.toLowerCase().endsWith(".pdf")
      );
      if (pdfFiles.length === 0) {
        setError("PDFファイルのみアップロードできます");
        return;
      }

      setUploading(true);
      try {
        const newLogs: UploadLog[] = [];
        for (const file of pdfFiles) {
          if (autoRename) {
            const res = await uploadFileAutoRename(file);
            newLogs.push({
              filename: res.filename,
              hinmei: res.hinmei,
              renamed: res.renamed,
            });
          } else {
            const res = await uploadFile(file);
            newLogs.push({ filename: res.filename, hinmei: null, renamed: false });
          }
        }
        setLogs(newLogs);
        onUploadComplete();
      } catch (e) {
        setError(e instanceof Error ? e.message : "アップロードに失敗しました");
      } finally {
        setUploading(false);
      }
    },
    [onUploadComplete, autoRename]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  };

  const onDragLeave = () => setDragging(false);

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    e.target.value = "";
  };

  return (
    <div>
      <label className="auto-rename-toggle">
        <input
          type="checkbox"
          checked={autoRename}
          onChange={(e) => { setAutoRename(e.target.checked); setLogs([]); setError(null); }}
        />
        アップロード時に品名を自動抽出してリネーム
      </label>

      <div
        className={`upload-area${dragging ? " dragging" : ""}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
      >
        <p>PDFファイルをドラッグ&ドロップ、またはクリックして選択</p>
        <label className="upload-label">
          <input
            type="file"
            accept=".pdf"
            multiple
            onChange={onChange}
            style={{ display: "none" }}
          />
          <span className="btn">ファイルを選択</span>
        </label>
        {uploading && (
          <p className="status-msg">
            {autoRename ? "アップロード・品名抽出中..." : "アップロード中..."}
          </p>
        )}
        {error && <p className="status-msg error">{error}</p>}
      </div>

      {logs.length > 0 && (
        <ul className="upload-log-list">
          {logs.map((log, i) => (
            <li key={i} className="upload-log-item">
              {log.renamed ? (
                <>
                  <span className="upload-log-icon">✅</span>
                  <span>
                    品名「{log.hinmei}」を検出 →{" "}
                    <span className="upload-log-filename">{log.filename}</span> にリネーム
                  </span>
                </>
              ) : autoRename ? (
                <>
                  <span className="upload-log-icon">⚠️</span>
                  <span>
                    品名が見つからず →{" "}
                    <span className="upload-log-filename">{log.filename}</span> でそのまま保存
                  </span>
                </>
              ) : (
                <>
                  <span className="upload-log-icon">📄</span>
                  <span className="upload-log-filename">{log.filename}</span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
