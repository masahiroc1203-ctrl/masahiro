import { useState } from "react";
import { FileInfo, batchRename, getContent } from "../api/client";
import { buildFilename, getStem } from "../utils/rename";

interface Props {
  files: FileInfo[];
  onClose: () => void;
  onRenamed: () => void;
}

type Keywords = { kw1: string; kw2: string; kw3: string };

interface FileExtractResult {
  kw1: { found: boolean; context: string } | null;
  kw2: { found: boolean; context: string } | null;
  kw3: { found: boolean; context: string } | null;
}

function searchInText(text: string, keyword: string): { found: boolean; context: string } {
  const kw = keyword.trim();
  if (!kw) return { found: false, context: "" };
  const idx = text.indexOf(kw);
  if (idx === -1) return { found: false, context: "" };
  const start = Math.max(0, idx - 15);
  const end = Math.min(text.length, idx + kw.length + 15);
  const context =
    (start > 0 ? "…" : "") +
    text.slice(start, end).replace(/\n/g, " ") +
    (end < text.length ? "…" : "");
  return { found: true, context };
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

  const handleExtractAll = async () => {
    setExtracting(true);
    setExtractResults(null);
    setConfirmed(new Set());
    try {
      const resultMap: Record<string, FileExtractResult> = {};
      for (const f of files) {
        const kw = keywords[f.filename] ?? { kw1: "", kw2: "", kw3: "" };
        if (!kw.kw1.trim() && !kw.kw2.trim() && !kw.kw3.trim()) continue;
        const content = await getContent(f.filename);
        const fullText = content.pages.map((p) => p.text).join("\n");
        resultMap[f.filename] = {
          kw1: kw.kw1.trim() ? searchInText(fullText, kw.kw1) : null,
          kw2: kw.kw2.trim() ? searchInText(fullText, kw.kw2) : null,
          kw3: kw.kw3.trim() ? searchInText(fullText, kw.kw3) : null,
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
        const kw = keywords[f.filename] ?? { kw1: "", kw2: "", kw3: "" };
        const newName = buildFilename(getStem(f.filename), kw.kw1, kw.kw2, kw.kw3, withStem);
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

  // キーワードあり & 確認済みのファイル数
  const confirmedCount = files.filter((f) => {
    const kw = keywords[f.filename];
    return (
      buildFilename(getStem(f.filename), kw?.kw1 ?? "", kw?.kw2 ?? "", kw?.kw3 ?? "", withStem) !== "" &&
      confirmed.has(f.filename)
    );
  }).length;

  // 抽出対象ファイル数（キーワードが1つ以上あるもの）
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
                  <input type="radio" checked={withStem} onChange={() => setWithStem(true)} />
                  元ファイル名 + キーワード
                </label>
                <label className="radio-label">
                  <input type="radio" checked={!withStem} onChange={() => setWithStem(false)} />
                  キーワードのみ
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
                    const preview = buildFilename(getStem(f.filename), kw.kw1, kw.kw2, kw.kw3, withStem);
                    const ex = extractResults?.[f.filename];
                    const hasKeyword = kw.kw1.trim() || kw.kw2.trim() || kw.kw3.trim();
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
                        <td className="batch-extract-col">
                          {ex ? (
                            <div className="batch-extract-results">
                              {(["kw1", "kw2", "kw3"] as const).map((k) => {
                                const r = ex[k];
                                if (!r) return null;
                                return (
                                  <div key={k} className={r.found ? "extract-found" : "extract-not-found"} title={r.context}>
                                    {r.found ? "✅" : "❌"} {kw[k]}
                                  </div>
                                );
                              })}
                            </div>
                          ) : (
                            <span className="extract-pending">
                              {hasKeyword && extractResults !== null ? "—" : ""}
                            </span>
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
