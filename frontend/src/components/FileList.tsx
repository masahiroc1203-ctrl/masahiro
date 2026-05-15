import { FileInfo, downloadFile } from "../api/client";

interface Props {
  files: FileInfo[];
  onRename: (filename: string) => void;
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

export default function FileList({ files, onRename }: Props) {
  if (files.length === 0) {
    return <p className="no-files">アップロードされたファイルはありません</p>;
  }

  return (
    <table className="file-table">
      <thead>
        <tr>
          <th>ファイル名</th>
          <th>サイズ</th>
          <th>更新日時</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {files.map((f) => (
          <tr key={f.filename}>
            <td className="filename-cell">{f.filename}</td>
            <td>{formatSize(f.size)}</td>
            <td>{formatDate(f.modified_at)}</td>
            <td className="action-cell">
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
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
