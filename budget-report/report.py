#!/usr/bin/env python3
"""SQLite の家計簿データベースから月次収支レポート(HTML)を生成するツール。

使い方:
    python3 report.py --db kakeibo.db --out report.html

自前の DB がデフォルトスキーマ(schema.sql)と異なる場合は --query で
date / amount / type / category の4列を返す SQL を指定してください。例:

    python3 report.py --db mydata.db --query "
        SELECT 日付 AS date, 金額 AS amount,
               CASE WHEN 区分 = '入金' THEN 'income' ELSE 'expense' END AS type,
               費目 AS category
        FROM 家計簿"

依存ライブラリなし(Python 標準ライブラリのみ)。出力 HTML も自己完結型で、
ブラウザで開くだけでチャートが表示されます。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

INCOME_TYPES = {"income", "収入", "in", "credit"}


def normalize(records, cols: list[str]) -> list[tuple[str, int, str, str]]:
    """(date, amount, type, category) を含む行の並びを内部形式に正規化する。"""
    cols = [c.lower() for c in cols]
    required = {"date", "amount", "type", "category"}
    missing = required - set(cols)
    if missing:
        sys.exit(f"エラー: 入力に列 {sorted(missing)} がありません(取得列: {cols})")
    idx = {c: cols.index(c) for c in required}
    rows = []
    for r in records:
        raw_date = str(r[idx["date"]])
        month = raw_date[:7]  # ISO 形式 (YYYY-MM-DD...) の先頭7文字
        if len(month) != 7 or month[4] != "-":
            sys.exit(f"エラー: date 列が ISO 形式 (YYYY-MM-DD) ではありません: {raw_date!r}")
        amount = int(round(float(r[idx["amount"]])))
        kind = "income" if str(r[idx["type"]]).lower() in INCOME_TYPES else "expense"
        category = str(r[idx["category"]] or "未分類")
        rows.append((month, abs(amount), kind, category))
    return rows


def load_sqlite(db: Path, query: str) -> list[tuple[str, int, str, str]]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = conn.execute(query)
        return normalize(cur.fetchall(), [c[0] for c in cur.description])
    finally:
        conn.close()


def load_postgres(dsn: str, query: str) -> list[tuple[str, int, str, str]]:
    try:
        import psycopg  # psycopg 3
    except ImportError:
        try:
            import psycopg2 as psycopg  # type: ignore[no-redef]
        except ImportError:
            sys.exit("エラー: PostgreSQL 接続には psycopg が必要です。\n"
                     "  pip install 'psycopg[binary]'   (または pip install psycopg2-binary)")
    try:
        conn = psycopg.connect(dsn)
    except Exception as e:  # psycopg2/3 で例外クラスが異なるため広めに捕捉
        sys.exit(
            "エラー: PostgreSQL に接続できませんでした。\n"
            "  よくある原因:\n"
            "   - データベースが起動していない → docker-compose up -d を実行してから再試行\n"
            "   - 接続先(ユーザー名・パスワード・DB名)が違う → --dsn の値を確認\n"
            f"  詳細: {e}"
        )
    try:
        cur = conn.cursor()
        cur.execute(query)
        return normalize(cur.fetchall(), [c[0] for c in cur.description])
    finally:
        conn.close()


def load_csv(path: Path) -> list[tuple[str, int, str, str]]:
    import csv
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            sys.exit(f"エラー: CSV が空です: {path}")
        return normalize(list(reader), header)


def month_range(start: str, end: str) -> list[str]:
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    months = []
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return months


def aggregate(rows: list[tuple[str, int, str, str]], limit_months: int) -> dict:
    income = defaultdict(int)
    expense = defaultdict(int)
    by_category = defaultdict(lambda: defaultdict(int))  # category -> month -> amount

    for month, amount, kind, category in rows:
        if kind == "income":
            income[month] += amount
        else:
            expense[month] += amount
            by_category[category][month] += amount

    months = month_range(min(income | expense), max(income | expense))
    if limit_months > 0:
        months = months[-limit_months:]

    cat_totals = {c: sum(by_category[c].get(mo, 0) for mo in months) for c in by_category}
    # 全カテゴリを金額の多い順に返す(集約せず、絞り込みはレポート側の凡例クリックで行う)
    categories = sorted((c for c in cat_totals if cat_totals[c] > 0), key=lambda c: -cat_totals[c])
    category_series = {c: [by_category[c].get(mo, 0) for mo in months] for c in categories}

    return {
        "months": months,
        "income": [income.get(mo, 0) for mo in months],
        "expense": [expense.get(mo, 0) for mo in months],
        "categories": categories,
        "categorySeries": category_series,
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="月次収支レポート(HTML)を生成")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--db", type=Path, help="SQLite データベースのパス")
    src.add_argument("--dsn", help="PostgreSQL 接続文字列(例: postgresql://user:pass@localhost:5432/kakeibo)")
    src.add_argument("--csv", type=Path,
                     help="date/amount/type/category 列を持つ CSV ファイルのパス")
    parser.add_argument("--out", type=Path, default=Path("report.html"), help="出力 HTML のパス")
    parser.add_argument("--table", default="transactions", help="読み取るテーブル名(デフォルトスキーマ用)")
    parser.add_argument("--query", default=None,
                        help="date/amount/type/category を返すカスタム SQL(自前スキーマ用)")
    parser.add_argument("--query-file", type=Path, default=None,
                        help="カスタム SQL を書いたファイルのパス(--query の代わりに使える)")
    parser.add_argument("--months", type=int, default=0,
                        help="直近 N ヶ月に限定(0 = 全期間。レポート内でも期間は絞り込み可能)")
    args = parser.parse_args()

    if args.query and args.query_file:
        sys.exit("エラー: --query と --query-file は同時に指定できません")
    if args.query_file:
        if not args.query_file.exists():
            sys.exit(f"エラー: SQL ファイルが見つかりません: {args.query_file}")
        query = args.query_file.read_text(encoding="utf-8")
    else:
        query = args.query or f'SELECT date, amount, type, category FROM "{args.table}"'
    if args.csv:
        if not args.csv.exists():
            sys.exit(f"エラー: CSV が見つかりません: {args.csv}")
        rows = load_csv(args.csv)
    elif args.dsn:
        rows = load_postgres(args.dsn, query)
    else:
        if not args.db.exists():
            sys.exit(f"エラー: データベースが見つかりません: {args.db}")
        rows = load_sqlite(args.db, query)
    if not rows:
        sys.exit("エラー: トランザクションが1件もありません")

    payload = aggregate(rows, args.months)
    template = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    # </script> によるタグ早期終了を防ぐ
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    args.out.write_text(template.replace("__PAYLOAD__", payload_json), encoding="utf-8")
    print(f"{args.out} を生成しました({len(payload['months'])}ヶ月分、{len(rows)}件を集計)")


if __name__ == "__main__":
    main()
