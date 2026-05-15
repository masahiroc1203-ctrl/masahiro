import { useCallback, useEffect, useState } from "react";
import { FileInfo, listFiles } from "./api/client";
import FileUpload from "./components/FileUpload";
import FileList from "./components/FileList";
import RenamePanel from "./components/RenamePanel";

export default function App() {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const fetchFiles = useCallback(async () => {
    setLoadError(null);
    try {
      const list = await listFiles();
      setFiles(list);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "ファイル一覧の取得に失敗しました");
    }
  }, []);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const handleUploadComplete = () => {
    fetchFiles();
  };

  const handleRename = (filename: string) => {
    setRenameTarget(filename);
  };

  const handleRenamed = () => {
    fetchFiles();
  };

  const handleClose = () => {
    setRenameTarget(null);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>PDF操作アプリ</h1>
      </header>

      <main className="app-main">
        <section className="section">
          <h2>ファイルアップロード</h2>
          <FileUpload onUploadComplete={handleUploadComplete} />
        </section>

        <section className="section">
          <h2>ファイル一覧</h2>
          {loadError ? (
            <p className="status-msg error">{loadError}</p>
          ) : (
            <FileList files={files} onRename={handleRename} />
          )}
        </section>
      </main>

      {renameTarget && (
        <RenamePanel
          filename={renameTarget}
          onClose={handleClose}
          onRenamed={handleRenamed}
        />
      )}
    </div>
  );
}
