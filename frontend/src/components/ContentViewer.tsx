import { useEffect, useState } from "react";
import { getContent, ContentResult } from "../api/client";

interface Props {
  filename: string;
  onClose: () => void;
}

export default function ContentViewer({ filename, onClose }: Props) {
  const [loading, setLoading] = useState(true);
  const [content, setContent] = useState<ContentResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getContent(filename)
      .then((result) => setContent(result))
      .catch((e) => setError(e instanceof Error ? e.message : "取得に失敗しました"))
      .finally(() => setLoading(false));
  }, [filename]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content content-viewer"
        onClick={(e) => e.stopPropagation()}
      >
        <h2>{filename} の内容</h2>
        {loading ? (
          <p className="status-msg">テキストを読み込み中...</p>
        ) : error ? (
          <p className="status-msg error">{error}</p>
        ) : content ? (
          <div className="content-pages">
            {content.pages.map((page) => (
              <div key={page.page_num} className="content-page">
                <p className="content-page-header">--- ページ {page.page_num} ---</p>
                <p className="content-page-text">
                  {page.text.trim() ? page.text : "(テキストなし)"}
                </p>
              </div>
            ))}
          </div>
        ) : null}
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            閉じる
          </button>
        </div>
      </div>
    </div>
  );
}
