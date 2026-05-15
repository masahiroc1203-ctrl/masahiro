import { useState } from "react";
import { FileInfo, batchRename } from "../api/client";
import { buildFilename } from "../utils/rename";

interface Props {
  files: FileInfo[];
  onClose: () => void;
  onRenamed: () => void;
}

type Keywords = { kw1: string; kw2: string; kw3: string };

export default function BatchRenamePanel({ files, onClose, onRenamed }: Props) {
  const [keywords, setKeywords] = useState<Record<string, Keywords>>(() =>
    Object.fromEntries(files.map((f) => [f.filename, { kw1: "", kw2: "", kw3: "" }]))
  );
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<{ old: string; new: string }[]>([]);
  const [errors, setErrors] = useState<{ filename: string; error: string }[]>([]);

  const setKw = (filename: string, key: keyof Keywords, value: string) => {
    setKeywords((prev) => ({
      ...prev,
      [filename]: { ...prev[filename], [key]: value },
    }));
  };

  const handleBatchRename = async () => {
    const renames = files
      .map((f) => {
        const kw = keywords[f.filename] ?? { kw1: "", kw2: "", kw3: "" };
        const newName = buildFilename(kw.kw1, kw.kw2, kw.kw3);
        return newName ? { original_filename: f.filename, new_filename: newName } : null;
      })
      .filter((r): r is NonNullable<typeof r> => r !== null);

    if (renames.length === 0) {
      return;
    }

    setRunning(true);
    setResults([]);
    setErrors([]);
    try {
      const res = await batchRename(renames);
      setResults(res.results.map((r) => ({ old: r.old_filename, new: r.new_filename })));
      setErrors(res.errors.map((e) => ({ filename: e.original_filename, error: e.error })));
      if (res.results.length > 0) {
        onRenamed();
      }
    } catch (e) {
      setErrors([{ filename: "—", error: e instanceof Error ? e.message : "一括リネームに失敗しました" }]);
    } finally {
      setRunning(false);
    }
  };

  const pendingCount = files.filter((f) => {
    const kw = keywords[f.filename];
    return buildFilename(kw?.kw1 ?? "", kw?.kw2 ?? "", kw?.kw3 ?? "") !== "";
  }).length;

  const isDone = results.length > 0 || errors.length > 0;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content batch-rename-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <h2>一括リネーム</h2>
        <p className="status-msg">キーワードを入力したファイルのみリネームされます。</p>

        {!isDone ? (
          <>
            <div className="batch-rename-table-wrap">
              <table className="batch-rename-table">
                <thead>
                  <tr>
                    <th>現在のファイル名</th>
                    <th>キーワード 1</th>
                    <th>キーワード 2</th>
                    <th>キーワード 3</th>
                    <th>新ファイル名プレビュー</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((f) => {
                    const kw = keywords[f.filename] ?? { kw1: "", kw2: "", kw3: "" };
                    const preview = buildFilename(kw.kw1, kw.kw2, kw.kw3);
                    return (
                      <tr key={f.filename}>
                        <td className="batch-orig-name">{f.filename}</td>
                        <td>
                          <input
                            type="text"
                            value={kw.kw1}
                            onChange={(e) => setKw(f.filename, "kw1", e.target.value)}
                            className="batch-kw-input"
                            placeholder="kw1"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            value={kw.kw2}
                            onChange={(e) => setKw(f.filename, "kw2", e.target.value)}
                            className="batch-kw-input"
                            placeholder="kw2"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            value={kw.kw3}
                            onChange={(e) => setKw(f.filename, "kw3", e.target.value)}
                            className="batch-kw-input"
                            placeholder="kw3"
                          />
                        </td>
                        <td className="batch-preview-name">{preview || "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="modal-actions">
              <button
                className="btn btn-primary"
                onClick={handleBatchRename}
                disabled={running || pendingCount === 0}
              >
                {running ? "実行中..." : `一括リネーム実行（${pendingCount}件）`}
              </button>
              <button className="btn btn-secondary" onClick={onClose}>
                キャンセル
              </button>
            </div>
          </>
        ) : (
          <>
            {results.length > 0 && (
              <div className="modal-field">
                <label>✅ 成功 ({results.length}件)</label>
                <ul className="result-list">
                  {results.map((r) => (
                    <li key={r.old}>{r.old} → {r.new}</li>
                  ))}
                </ul>
              </div>
            )}
            {errors.length > 0 && (
              <div className="modal-field">
                <label>❌ エラー ({errors.length}件)</label>
                <ul className="result-list error-list">
                  {errors.map((e, i) => (
                    <li key={i}>{e.filename}: {e.error}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={onClose}>
                閉じる
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
