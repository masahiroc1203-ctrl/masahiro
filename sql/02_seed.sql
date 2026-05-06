-- デフォルトユーザー
INSERT INTO users (name) VALUES ('default')
ON CONFLICT (name) DO NOTHING;

-- 支払い手段
INSERT INTO providers (name) VALUES
    ('楽天カード'),
    ('PayPay')
ON CONFLICT (name) DO NOTHING;

-- 大分類
INSERT INTO categories (name) VALUES
    ('食費'),
    ('交通費'),
    ('日用品'),
    ('娯楽'),
    ('医療・健康'),
    ('通信'),
    ('光熱費'),
    ('その他')
ON CONFLICT (name) DO NOTHING;

-- 中分類
INSERT INTO subcategories (category_id, name) VALUES
    ((SELECT id FROM categories WHERE name = '食費'), '外食'),
    ((SELECT id FROM categories WHERE name = '食費'), 'スーパー'),
    ((SELECT id FROM categories WHERE name = '食費'), 'コンビニ'),
    ((SELECT id FROM categories WHERE name = '交通費'), '電車・バス'),
    ((SELECT id FROM categories WHERE name = '交通費'), 'タクシー'),
    ((SELECT id FROM categories WHERE name = '交通費'), '駐車場'),
    ((SELECT id FROM categories WHERE name = '娯楽'), '動画・音楽'),
    ((SELECT id FROM categories WHERE name = '娯楽'), 'ゲーム'),
    ((SELECT id FROM categories WHERE name = '娯楽'), 'ショッピング')
ON CONFLICT (category_id, name) DO NOTHING;
