-- ローカル PostgreSQL DB(expense / コンテナ expense-db)用のアダプタクエリ。
-- transactions + categories を report.py が期待する4列
-- (date / amount / type / category)に変換します。
--
-- 使い方:
--   python report.py --dsn postgresql://postgres:secret@localhost:5432/expense \
--       --query-file queries/postgres-local-db.sql --out report.html
--
-- スキーマ対応メモ(実 DB を確認して作成):
--   - 日付列は used_on(occurred_at ではない)
--   - 金額 amount は常に正の整数。収入/支出は direction 列で区別する
--       direction = 'in'       … 収入
--       direction = 'out'      … 支出
--       direction = 'transfer' … 口座間振替(収支ではないため集計から除外)
--   - currency 列は存在しない
SELECT
    t.used_on                                                     AS date,
    t.amount                                                      AS amount,
    CASE WHEN t.direction = 'in' THEN 'income' ELSE 'expense' END AS type,
    COALESCE(c.name, '未分類')                                    AS category
FROM transactions t
LEFT JOIN categories c ON c.id = t.category_id
WHERE t.direction IN ('in', 'out')
