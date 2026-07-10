-- 家計簿トランザクションテーブル(デフォルトスキーマ)
-- 自前の DB が別スキーマの場合は report.py の --query で列名をマッピングできます。
CREATE TABLE IF NOT EXISTS transactions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    date     TEXT    NOT NULL,              -- ISO 形式 (YYYY-MM-DD)
    amount   INTEGER NOT NULL CHECK (amount >= 0),  -- 金額(円、正の値)
    type     TEXT    NOT NULL CHECK (type IN ('income', 'expense', '収入', '支出')),
    category TEXT    NOT NULL DEFAULT '未分類',
    memo     TEXT
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions (date);
