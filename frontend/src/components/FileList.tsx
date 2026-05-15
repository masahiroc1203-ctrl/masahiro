import { FileInfo, downloadFile } from "../api/client";

interface Props {
  files: FileInfo[];
  selectedForMerge: Set<string>;
  onToggleMerge: (filename: string, checked: boolean) => void;
  onRename: (filename: string) => void;
  onViewContent: (filename: string) => void;
  onSplit: (filename: string) => void;
  onMoveUp: (filename: string) => void;
  onMoveDown: (filename: string) => void;
  onClearAll: () => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("ja-JP");
}

export default function FileList({ files, selectedForMerge, onToggleMerge, onRename, onViewContent, onSplit, onMoveUp, onMoveDown, onClearAll }: Props) {
  if (files.length === 0) {
    return <p className="no-files">アップロードされたファイルはありません</p>;
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "8px" }}>
        <button className="btn btn-danger" onClick={onClearAll}>
          🗑 全削除
        </button>
      </div>
      <table className="file-table">
        <thead>
          <tr>
            <th className="merge-col">結合</th>
            <th>ファイル名</th>
            <th>サイズ</th>
            <th>更新日時</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {files.map((f, index) => (
            <tr key={f.filename}>
              <td className="merge-col">
                <input
                  type="checkbox"
                  checked={selectedForMerge.has(f.filename)}
                  onChange={(e) => onToggleMerge(f.filename, e.target.checked)}
                />
              </td>
              <td className="filename-cell">{f.filename}</td>
              <td>{formatSize(f.size)}</td>
              <td>{formatDate(f.modified_at)}</td>
              <td className="action-cell">
                <button
                  className="btn btn-sm"
                  onClick={() => onMoveUp(f.filename)}
                  disabled={index === 0}
                >
                  ↑
                </button>
                <button
                  className="btn btn-sm"
                  onClick={() => onMoveDown(f.filename)}
                  disabled={index === files.length - 1}
                >
                  ↓
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => downloadFile(f.filename)}
                >
                  ダウンロード
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => onRename(f.filename)}
                >
                  リネーム
                </button>
                <button
                  className="btn btn-view-content"
                  onClick={() => onViewContent(f.filename)}
                >
                  内容表示
                </button>
                <button
                  className="btn btn-split"
                  onClick={() => onSplit(f.filename)}
                >
                  分割
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
