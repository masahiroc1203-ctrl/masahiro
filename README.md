# expense DB ローカル環境

## 構成

```
.
├── docker-compose.yml       # PostgreSQL コンテナ定義
├── sql/
│   ├── 01_schema.sql        # テーブル定義
│   └── 02_seed.sql          # 初期データ（users / providers / categories）
└── scripts/
    ├── import_csv.py        # CSV インポートスクリプト
    └── requirements.txt
```

---

## セットアップ手順

### 1. Docker コンテナ起動

```bash
docker-compose up -d
```

> `sql/` フォルダ内の SQL は初回起動時に自動実行されます。
> すでにデータがある場合は自動実行されません（手動で実行してください）。

### 2. 手動でスキーマ・初期データを適用する場合

```bash
docker exec -i expense_db psql -U appuser -d expense < sql/01_schema.sql
docker exec -i expense_db psql -U appuser -d expense < sql/02_seed.sql
```

### 3. DBeaver 接続設定

| 項目 | 値 |
|------|-----|
| ホスト | localhost |
| ポート | 5432 |
| データベース | expense |
| ユーザー | appuser |
| パスワード | secret |

---

## CSV インポート

### インストール

```bash
pip install -r scripts/requirements.txt
```

### 使い方

CSVを `C:\expense-import\import\` に置いて実行：

```bash
python scripts/import_csv.py
```

オプション：

```bash
# フォルダを指定する場合
python scripts/import_csv.py --import-dir "C:\expense-import\import"

# 処理済みファイルを移動しない場合
python scripts/import_csv.py --no-move
```

### 動作

- `import/` フォルダの `.csv` / `.CSV` を自動検出
- 楽天カード・PayPay のフォーマットを自動判定
- Shift-JIS / UTF-8 を自動判定
- 同日・同金額・同メモの重複はスキップ
- 処理済み → `import/done/` に移動
- エラー → `import/error/` に移動

---

## テーブル構成

```
users          ユーザー
providers      支払い手段（楽天カード, PayPay, etc.）
categories     大分類（食費, 交通費, etc.）
subcategories  中分類（外食, スーパー, etc.）
transactions   明細（CSVインポート・手動入力）
```
