# budget-report — 月次収支レポート生成ツール

家計簿データベース(SQLite / PostgreSQL / CSV)から毎月の収支を集計し、
ブラウザで開くだけで見られる自己完結型の HTML レポート(チャート付き)を
生成するツールです。

- 依存ライブラリなし(Python 3.9+ の標準ライブラリのみ。PostgreSQL 接続時のみ psycopg が必要)
- 出力 HTML も外部読み込みなしの1ファイル。オフラインで開けます
- ダークモード対応・ホバーで各月の詳細をツールチップ表示

## レポートの内容

| セクション | 内容 |
|---|---|
| KPI タイル | 最新月の収入・支出・収支(前月比と収支の12ヶ月スパークライン付き) |
| 収入と支出の推移 | 月ごとのグループ棒グラフ |
| 月次収支 | 収入 − 支出 を 0 基準の上下棒で表示(黒字=青、赤字=赤) |
| カテゴリ別支出の内訳 | 月ごとの積み上げ棒グラフ(上位7カテゴリ+その他)。凡例クリックで1カテゴリを強調表示 |
| カテゴリ別支出の合計 | 選択期間の合計を多い順の横棒で表示(金額・構成比・月平均) |
| 月次サマリー | 全数値の一覧表 |

期間はレポート内のボタン(直近6ヶ月 / 12ヶ月 / 全期間)で切り替えられます。

## クイックスタート

```bash
cd budget-report

# 1. サンプルデータベースを生成(動作確認用)
python3 sample_data.py            # → sample.db

# 2. レポートを生成
python3 report.py --db sample.db --out report.html

# 3. report.html をブラウザで開く
```

## 自前のデータベースで使う

### デフォルトスキーマの場合

`schema.sql` の `transactions` テーブル(date / amount / type / category)を
使っている場合はそのまま動きます:

```bash
python3 report.py --db kakeibo.db --out report.html
```

- `date` … ISO 形式(`YYYY-MM-DD`)
- `amount` … 金額(円、正の整数)
- `type` … `income` / `expense`(`収入` / `支出` も可)
- `category` … 費目名(任意の文字列)

テーブル名だけ違う場合は `--table 家計簿` のように指定できます。

### スキーマが異なる場合(--query)

`date` / `amount` / `type` / `category` の4列を返す SQL を渡せば、
どんなスキーマでも集計できます:

```bash
python3 report.py --db mydata.db --out report.html --query "
  SELECT 日付 AS date,
         金額 AS amount,
         CASE WHEN 区分 = '入金' THEN 'income' ELSE 'expense' END AS type,
         費目 AS category
  FROM 家計簿"
```

複数テーブルに分かれている場合も `UNION ALL` で結合すれば OK です。

## 実データ(PostgreSQL)を参照する

ローカルの PostgreSQL(`sql/01_schema.sql` のスキーマ)を直接参照できます。
データのあるマシン上で実行してください:

```bash
pip install 'psycopg[binary]'   # 初回のみ

python3 report.py \
  --dsn postgresql://ユーザー名:パスワード@localhost:5432/データベース名 \
  --query "$(cat queries/postgres-local-db.sql)" \
  --out report.html
```

`queries/postgres-local-db.sql` が transactions + categories を
このツールの形式に変換します。このスキーマには収入/支出の区分列がないため、
**金額がマイナスの行を収入**とみなしています。収入の記録方法が違う場合は
クエリ内の CASE 式を調整してください。

### CSV 経由で参照する(リモートセッションにデータを渡す場合)

Claude Code のクラウドセッションなど、DB に直接つなげない環境で集計したい
場合は、CSV にエクスポートしてリポジトリに含めるのが簡単です:

```bash
psql -d データベース名 -c "\copy (
  SELECT t.occurred_at::date AS date,
         ABS(t.amount) AS amount,
         CASE WHEN t.amount < 0 THEN 'income' ELSE 'expense' END AS type,
         COALESCE(c.name, '未分類') AS category
  FROM transactions t
  LEFT JOIN categories c ON c.id = t.category_id
) TO 'transactions.csv' WITH CSV HEADER"

python3 report.py --csv transactions.csv --out report.html
```

家計データを含む CSV をコミットする場合は、リポジトリが非公開であることを
確認してください。

### オプション一覧

| オプション | 説明 | デフォルト |
|---|---|---|
| `--db` | SQLite データベースのパス | — |
| `--dsn` | PostgreSQL 接続文字列 | — |
| `--csv` | CSV ファイルのパス(date/amount/type/category 列) | — |
| `--out` | 出力 HTML のパス | `report.html` |
| `--table` | 読み取るテーブル名 | `transactions` |
| `--query` | カスタム SQL(`--table` より優先) | — |
| `--months` | 直近 N ヶ月に限定(0 = 全期間) | `0` |

`--db` / `--dsn` / `--csv` はいずれか1つを指定します。

## 定期的に更新する

cron 等で回せば常に最新のレポートが手元に置けます:

```cron
0 6 * * * cd /path/to/budget-report && python3 report.py --db ~/kakeibo.db --out ~/report.html
```

## ファイル構成

```
budget-report/
├── report.py        # 集計 + HTML 生成(CLI 本体)
├── template.html    # レポートのテンプレート(チャート描画ロジック込み)
├── schema.sql       # デフォルトスキーマ(SQLite)
├── queries/
│   └── postgres-local-db.sql  # ローカル PostgreSQL 用アダプタクエリ
├── sample_data.py   # サンプル DB 生成スクリプト
└── README.md
```
