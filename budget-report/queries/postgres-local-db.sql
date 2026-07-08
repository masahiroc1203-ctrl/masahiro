-- ローカル PostgreSQL DB(sql/01_schema.sql のスキーマ)用のアダプタクエリ。
-- transactions + categories を report.py の期待する4列に変換します。
--
-- 使い方:
--   python3 report.py --dsn postgresql://user:pass@localhost:5432/kakeibo \
--       --query "$(cat queries/postgres-local-db.sql)"
--
-- 注意: このスキーマには収入/支出の区分列がないため、
-- 「金額がマイナス = 収入」とみなしています。
-- 収入を別の方法(専用カテゴリなど)で記録している場合は CASE 式を調整してください。
SELECT
    t.occurred_at::date                                      AS date,
    ABS(t.amount)                                            AS amount,
    CASE WHEN t.amount < 0 THEN 'income' ELSE 'expense' END  AS type,
    COALESCE(c.name, '未分類')                               AS category
FROM transactions t
LEFT JOIN categories c ON c.id = t.category_id
WHERE t.currency = 'JPY'
