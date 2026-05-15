import { useCallback, useEffect, useState } from "react";
import { FileInfo, listFiles, clearAllFiles } from "./api/client";
import FileUpload from "./components/FileUpload";
import FileList from "./components/FileList";
import RenamePanel from "./components/RenamePanel";
import BatchRenamePanel from "./components/BatchRenamePanel";
import ContentViewer from "./components/ContentViewer";
import MergePanel from "./components/MergePanel";
import SplitPanel from "./components/SplitPanel";

export default function App() {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [selectedForMerge, setSelectedForMerge] = useState<Set<string>>(new Set());
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [contentTarget, setContentTarget] = useState<string | null>(null);
  const [splitTarget, setSplitTarget] = useState<string | null>(null);
  const [showMerge, setShowMerge] = useState(false);
  const [showBatchRename, setShowBatchRename] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const fetchFiles = useCallback(async () => {
    setLoadError(null);
    try {
      const list = await listFiles();
      setFiles(list);
      // 取得後、存在しないファイルのチェックを外す
      setSelectedForMerge((prev) => {
        const names = new Set(list.map((f) => f.filename));
        const next = new Set([...prev].filter((n) => names.has(n)));
        return next;
      });
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "ファイル一覧の取得に失敗しました");
    }
  }, []);

  const handleMoveUp = (filename: string) => {
    setFiles((prev) => {
      const idx = prev.findIndex((f) => f.filename === filename);
      if (idx <= 0) return prev;
      const next = [...prev];
      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
      return next;
    });
  };

  const handleMoveDown = (filename: string) => {
    setFiles((prev) => {
      const idx = prev.findIndex((f) => f.filename === filename);
      if (idx < 0 || idx >= prev.length - 1) return prev;
      const next = [...prev];
      [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
      return next;
    });
  };

  const handleClearAll = async () => {
    if (!window.confirm("全てのファイルを削除しますか？")) return;
    try {
      await clearAllFiles();
      fetchFiles();
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "ファイルの削除に失敗しました");
    }
  };

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

  const handleToggleMerge = (filename: string, checked: boolean) => {
    setSelectedForMerge((prev) => {
      const next = new Set(prev);
      if (checked) next.add(filename);
      else next.delete(filename);
      return next;
    });
  };

  const handleOpenMerge = () => {
    setShowMerge(true);
  };

  const handleOpenBatchRename = () => {
    setShowBatchRename(true);
  };

  const handleCloseBatchRename = () => {
    setShowBatchRename(false);
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
          <button
            className="btn btn-merge"
            onClick={handleOpenMerge}
            disabled={selectedForMerge.size < 2}
            title={selectedForMerge.size < 2 ? "2件以上チェックしてください" : ""}
          >
            PDFを結合 {selectedForMerge.size >= 2 ? `(${selectedForMerge.size}件)` : ""}
          </button>
          <button
            className="btn btn-batch-rename"
            onClick={handleOpenBatchRename}
            disabled={files.length === 0}
          >
            一括リネーム
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
              selectedForMerge={selectedForMerge}
              onToggleMerge={handleToggleMerge}
              onRename={handleRename}
              onViewContent={handleViewContent}
              onSplit={handleSplit}
              onMoveUp={handleMoveUp}
              onMoveDown={handleMoveDown}
              onClearAll={handleClearAll}
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
          filesToMerge={files.filter((f) => selectedForMerge.has(f.filename))}
          onClose={handleCloseMerge}
          onMerged={handleMerged}
        />
      )}

      {showBatchRename && (
        <BatchRenamePanel
          files={files}
          onClose={handleCloseBatchRename}
          onRenamed={fetchFiles}
        />
      )}
    </div>
  );
}
