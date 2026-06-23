import { useState } from "react";
import { executeRename, extractKeyword } from "../api/client";
import { buildFilename, getStem } from "../utils/rename";

interface Props {
  filename: string;
  onClose: () => void;
  onRenamed: () => void;
}

interface ExtractResult {
  keyword: string;
  value: string | null;
}

export default function RenamePanel({ filename, onClose, onRenamed }: Props) {
  const stem = getStem(filename);
  const [kw1, setKw1] = useState("");
  const [kw2, setKw2] = useState("");
  const [kw3, setKw3] = useState("");
  const [withStem, setWithStem] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [extractResults, setExtractResults] = useState<ExtractResult[] | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);

  const keywords = [kw1, kw2, kw3].filter((k) => k.trim());

  // 抽出した値でプレビューを作成
  const previewFromExtracted = (): string => {
    if (!extractResults) return "";
    const [v1, v2, v3] = extractResults.map((r) => r.value ?? "");
    return buildFilename(stem, v1, v2, v3, withStem);
  };
  const preview = previewFromExtracted();

  const handleExtract = async () => {
    if (keywords.length === 0) {
      setError("少なくともキーワード1を入力してください");
      return;
    }
    setError(null);
    setExtractResults(null);
    setConfirmed(false);
    setExtracting(true);
    try {
      const activeKws = [kw1, kw2, kw3].filter((k) => k.trim());
      const results = await Promise.all(activeKws.map((k) => extractKeyword(filename, k)));
      setExtractResults(results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "抽出に失敗しました");
    } finally {
      setExtracting(false);
    }
  };

  const handleRename = async () => {
    setRenaming(true);
    setError(null);
    try {
      await executeRename(filename, preview);
      onRenamed();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "リネームに失敗しました");
    } finally {
      setRenaming(false);
    }
  };

  const handleKwChange = (setter: (v: string) => void) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setter(e.target.value);
    setExtractResults(null);
    setConfirmed(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>ファイルのリネーム</h2>

        <div className="modal-field">
          <label>現在のファイル名</label>
          <p className="current-filename">{filename}</p>
        </div>

        <div className="modal-field">
          <label>ファイル名の形式</label>
          <div className="radio-group">
            <label className="radio-label">
              <input type="radio" checked={withStem} onChange={() => { setWithStem(true); setExtractResults(null); setConfirmed(false); }} />
              元ファイル名 + 抽出値（例: {stem}_フロントプレート.pdf）
            </label>
            <label className="radio-label">
              <input type="radio" checked={!withStem} onChange={() => { setWithStem(false); setExtractResults(null); setConfirmed(false); }} />
              抽出値のみ（例: フロントプレート.pdf）
            </label>
          </div>
        </div>

        <div className="modal-field keyword-grid">
          <label>検索キーワード 1 <span className="required">*</span></label>
          <input
            type="text"
            value={kw1}
            onChange={handleKwChange(setKw1)}
            className="filename-input"
            placeholder="例: 品名"
          />
          <label>検索キーワード 2</label>
          <input
            type="text"
            value={kw2}
            onChange={handleKwChange(setKw2)}
            className="filename-input"
            placeholder="例: 材質（省略可）"
          />
          <label>検索キーワード 3</label>
          <input
            type="text"
            value={kw3}
            onChange={handleKwChange(setKw3)}
            className="filename-input"
            placeholder="例: 図番（省略可）"
          />
        </div>

        <div className="modal-actions" style={{ marginTop: 8 }}>
          <button
            className="btn btn-extract"
            onClick={handleExtract}
            disabled={extracting || keywords.length === 0}
          >
            {extracting ? "抽出中..." : "抽出"}
          </button>
        </div>

        {extractResults && (
          <div className="modal-field extract-results">
            <label>抽出結果</label>
            <ul className="extract-result-list">
              {extractResults.map((r) => (
                <li key={r.keyword} className={r.value ? "extract-found" : "extract-not-found"}>
                  <span className="extract-icon">{r.value ? "✅" : "❌"}</span>
                  <span className="extract-keyword">「{r.keyword}」</span>
                  {r.value
                    ? <span className="extract-context">→ {r.value}</span>
                    : <span className="extract-context">ファイル内に見つかりませんでした</span>
                  }
                </li>
              ))}
            </ul>
            <label className="confirm-check-label">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              上記の内容を確認しました
            </label>
          </div>
        )}

        {extractResults && (
          <div className="modal-field">
            <label>新しいファイル名（プレビュー）</label>
            <p className="hinmei-value">{preview || "— （値を抽出できませんでした）"}</p>
          </div>
        )}

        {error && <p className="status-msg error">{error}</p>}

        <div className="modal-actions">
          <button
            className="btn btn-primary"
            onClick={handleRename}
            disabled={renaming || !preview || !confirmed}
            title={!confirmed ? "抽出結果を確認してチェックを入れてください" : ""}
          >
            {renaming ? "実行中..." : "リネーム実行"}
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            キャンセル
          </button>
        </div>
      </div>
    </div>
  );
}
