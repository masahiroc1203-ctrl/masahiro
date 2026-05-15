import { useCallback, useState } from "react";
import { uploadFile } from "../api/client";

interface Props {
  onUploadComplete: () => void;
}

export default function FileUpload({ onUploadComplete }: Props) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      setError(null);
      setMessage(null);

      const pdfFiles = Array.from(files).filter((f) =>
        f.name.toLowerCase().endsWith(".pdf")
      );
      if (pdfFiles.length === 0) {
        setError("PDFファイルのみアップロードできます");
        return;
      }

      setUploading(true);
      try {
        for (const file of pdfFiles) {
          await uploadFile(file);
        }
        setMessage(`${pdfFiles.length}件のファイルをアップロードしました`);
        onUploadComplete();
      } catch (e) {
        setError(e instanceof Error ? e.message : "アップロードに失敗しました");
      } finally {
        setUploading(false);
      }
    },
    [onUploadComplete]
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
      {uploading && <p className="status-msg">アップロード中...</p>}
      {message && <p className="status-msg success">{message}</p>}
      {error && <p className="status-msg error">{error}</p>}
    </div>
  );
}
