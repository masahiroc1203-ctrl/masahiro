import { useState } from "react";
import { FileInfo, batchRename, extractKeyword } from "../api/client";
import { buildFilename, getStem } from "../utils/rename";

interface Props {
  files: FileInfo[];
  onClose: () => void;
  onRenamed: () => void;
}

type Keywords = { kw1: string; kw2: string; kw3: string };

interface FileExtractResult {
  kw1: { value: string | null } | null;
  kw2: { value: string | null } | null;
  kw3: { value: string | null } | null;
}

export default function BatchRenamePanel({ files, onClose, onRenamed }: Props) {
  const [keywords, setKeywords] = useState<Record<string, Keywords>>(() =>
    Object.fromEntries(files.map((f) => [f.filename, { kw1: "", kw2: "", kw3: "" }]))
  );
  const [withStem, setWithStem] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [extractResults, setExtractResults] = useState<Record<string, FileExtractResult> | null>(null);
  const [confirmed, setConfirmed] = useState<Set<string>>(new Set());
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<{ old: string; new: string }[]>([]);
  const [errors, setErrors] = useState<{ filename: string; error: string }[]>([]);

  const setKw = (filename: string, key: keyof Keywords, value: string) => {
    setKeywords((prev) => ({ ...prev, [filename]: { ...prev[filename], [key]: value } }));
    setExtractResults(null);
    setConfirmed(new Set());
  };

  const getExtractedValues = (filename: string) => {
    const ex = extractResults?.[filename];
    if (!ex) return null;
    return {
      v1: ex.kw1?.value ?? null,
      v2: ex.kw2?.value ?? null,
      v3: ex.kw3?.value ?? null,
    };
  };

  const buildPreview = (filename: string): string => {
    const vals = getExtractedValues(filename);
    if (!vals) return "";
    return buildFilename(getStem(filename), vals.v1 ?? "", vals.v2 ?? "", vals.v3 ?? "", withStem);
  };

  const handleExtractAll = async () => {
    setExtracting(true);
    setExtractResults(null);
    setConfirmed(new Set());
    try {
      const resultMap: Record<string, FileExtractResult> = {};
      for (const f of files) {
        const kw = keywords[f.filename] ?? { kw1: "", kw2: "", kw3: "" };
        if (!kw.kw1.trim() && !kw.kw2.trim() && !kw.kw3.trim()) continue;
        const [r1, r2, r3] = await Promise.all([
          kw.kw1.trim() ? extractKeyword(f.filename, kw.kw1) : Promise.resolve(null),
          kw.kw2.trim() ? extractKeyword(f.filename, kw.kw2) : Promise.resolve(null),
          kw.kw3.trim() ? extractKeyword(f.filename, kw.kw3) : Promise.resolve(null),
        ]);
        resultMap[f.filename] = {
          kw1: r1 ? { value: r1.value } : null,
          kw2: r2 ? { value: r2.value } : null,
          kw3: r3 ? { value: r3.value } : null,
        };
      }
      setExtractResults(resultMap);
    } catch (e) {
      setErrors([{ filename: "—", error: e instanceof Error ? e.message : "抽出に失敗しました" }]);
    } finally {
      setExtracting(false);
    }
  };

  const toggleConfirm = (filename: string, checked: boolean) => {
    setConfirmed((prev) => {
      const next = new Set(prev);
      if (checked) next.add(filename);
      else next.delete(filename);
      return next;
    });
  };

  const handleBatchRename = async () => {
    const renames = files
      .map((f) => {
        const newName = buildPreview(f.filename);
        return newName && confirmed.has(f.filename)
          ? { original_filename: f.filename, new_filename: newName }
          : null;
      })
      .filter((r): r is NonNullable<typeof r> => r !== null);

    if (renames.length === 0) return;
    setRunning(true);
    setResults([]);
    setErrors([]);
    try {
      const res = await batchRename(renames);
      setResults(res.results.map((r) => ({ old: r.old_filename, new: r.new_filename })));
      setErrors(res.errors.map((e) => ({ filename: e.original_filename, error: e.error })));
      if (res.results.length > 0) onRenamed();
    } catch (e) {
      setErrors([{ filename: "—", error: e instanceof Error ? e.message : "一括リネームに失敗しました" }]);
    } finally {
      setRunning(false);
    }
  };

  const confirmedCount = files.filter((f) => {
    return buildPreview(f.filename) !== "" && confirmed.has(f.filename);
  }).length;

  const extractTargetCount = files.filter((f) => {
    const kw = keywords[f.filename];
    return kw?.kw1.trim() || kw?.kw2.trim() || kw?.kw3.trim();
  }).length;

  const isDone = results.length > 0 || (errors.length > 0 && running === false && results.length === 0);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content batch-rename-panel" onClick={(e) => e.stopPropagation()}>
        <h2>一括リネーム</h2>

        {!isDone ? (
          <>
            <div className="modal-field">
              <label>ファイル名の形式</label>
              <div className="radio-group">
                <label className="radio-label">
                  <input type="radio" checked={withStem} onChange={() => { setWithStem(true); setExtractResults(null); setConfirmed(new Set()); }} />
                  元ファイル名 + 抽出値
                </label>
                <label className="radio-label">
                  <input type="radio" checked={!withStem} onChange={() => { setWithStem(false); setExtractResults(null); setConfirmed(new Set()); }} />
                  抽出値のみ
                </label>
              </div>
            </div>

            <div className="batch-rename-table-wrap">
              <table className="batch-rename-table">
                <thead>
                  <tr>
                    <th>ファイル名</th>
                    <th>キーワード 1</th>
                    <th>キーワード 2</th>
                    <th>キーワード 3</th>
                    <th>抽出結果</th>
                    <th>新ファイル名</th>
                    <th>確認</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((f) => {
                    const kw = keywords[f.filename] ?? { kw1: "", kw2: "", kw3: "" };
                    const ex = extractResults?.[f.filename];
                    const preview = buildPreview(f.filename);
                    return (
                      <tr key={f.filename}>
                        <td className="batch-orig-name">{f.filename}</td>
                        <td>
                          <input
                            type="text"
                            value={kw.kw1}
                            onChange={(e) => setKw(f.filename, "kw1", e.target.value)}
                            className="batch-kw-input"
                            placeholder="例: 品名"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            value={kw.kw2}
                            onChange={(e) => setKw(f.filename, "kw2", e.target.value)}
                            className="batch-kw-input"
                            placeholder="例: 材質"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            value={kw.kw3}
                            onChange={(e) => setKw(f.filename, "kw3", e.target.value)}
                            className="batch-kw-input"
                            placeholder="例: 図番"
                          />
                        </td>
                        <td className="batch-extract-col">
                          {ex ? (
                            <div className="batch-extract-results">
                              {(["kw1", "kw2", "kw3"] as const).map((k) => {
                                const r = ex[k];
                                if (!r) return null;
                                return (
                                  <div key={k} className={r.value ? "extract-found" : "extract-not-found"}>
                                    {r.value ? "✅" : "❌"} {kw[k]} → {r.value ?? "見つからず"}
                                  </div>
                                );
                              })}
                            </div>
                          ) : (
                            <span className="extract-pending" />
                          )}
                        </td>
                        <td className="batch-preview-name">{preview || "—"}</td>
                        <td className="batch-confirm-col">
                          {ex && preview ? (
                            <input
                              type="checkbox"
                              checked={confirmed.has(f.filename)}
                              onChange={(e) => toggleConfirm(f.filename, e.target.checked)}
                            />
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {errors.length > 0 && (
              <div className="modal-field">
                <p className="status-msg error">{errors[0].error}</p>
              </div>
            )}

            <div className="modal-actions">
              <button
                className="btn btn-extract"
                onClick={handleExtractAll}
                disabled={extracting || extractTargetCount === 0}
              >
                {extracting ? "抽出中..." : `一括抽出（${extractTargetCount}件）`}
              </button>
              <button
                className="btn btn-primary"
                onClick={handleBatchRename}
                disabled={running || confirmedCount === 0}
                title={confirmedCount === 0 ? "抽出して確認チェックを入れてください" : ""}
              >
                {running ? "実行中..." : `一括リネーム実行（${confirmedCount}件）`}
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
              <button className="btn btn-secondary" onClick={onClose}>閉じる</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
