import { useCallback, useEffect, useState } from "react";
import { FileInfo, listFiles } from "./api/client";
import FileUpload from "./components/FileUpload";
import FileList from "./components/FileList";
import RenamePanel from "./components/RenamePanel";
import ContentViewer from "./components/ContentViewer";
import MergePanel from "./components/MergePanel";
import SplitPanel from "./components/SplitPanel";

export default function App() {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [contentTarget, setContentTarget] = useState<string | null>(null);
  const [splitTarget, setSplitTarget] = useState<string | null>(null);
  const [showMerge, setShowMerge] = useState(false);
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

  const handleCloseRename = () => {
    setRenameTarget(null);
  };

  const handleViewContent = (filename: string) => {
    setContentTarget(filename);
  };

  const handleCloseContent = () => {
    setContentTarget(null);
  };

  const handleSplit = (filename: string) => {
    setSplitTarget(filename);
  };

  const handleSplitDone = () => {
    fetchFiles();
  };

  const handleCloseSplit = () => {
    setSplitTarget(null);
  };

  const handleOpenMerge = () => {
    setShowMerge(true);
  };

  const handleCloseMerge = () => {
    setShowMerge(false);
  };

  const handleMerged = () => {
    fetchFiles();
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-row">
          <h1>PDF操作アプリ</h1>
          <button className="btn btn-merge" onClick={handleOpenMerge}>
            PDFを結合
          </button>
        </div>
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
            <FileList
              files={files}
              onRename={handleRename}
              onViewContent={handleViewContent}
              onSplit={handleSplit}
            />
          )}
        </section>
      </main>

      {renameTarget && (
        <RenamePanel
          filename={renameTarget}
          onClose={handleCloseRename}
          onRenamed={handleRenamed}
        />
      )}

      {contentTarget && (
        <ContentViewer
          filename={contentTarget}
          onClose={handleCloseContent}
        />
      )}

      {splitTarget && (
        <SplitPanel
          filename={splitTarget}
          onClose={handleCloseSplit}
          onSplit={handleSplitDone}
        />
      )}

      {showMerge && (
        <MergePanel
          files={files}
          onClose={handleCloseMerge}
          onMerged={handleMerged}
        />
      )}
    </div>
  );
}
