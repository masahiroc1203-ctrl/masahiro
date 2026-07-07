#!/usr/bin/env python3
"""サンプルの家計簿データベースを生成するスクリプト。

使い方:
    python3 sample_data.py [出力先.db]   # デフォルト: sample.db

約14ヶ月分の収入・支出トランザクションを乱数で生成します。
report.py の動作確認用です。
"""
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

EXPENSE_CATEGORIES = {
    "住居費": (85000, 85000),   # 固定
    "食費": (48000, 72000),
    "水道光熱費": (9000, 18000),
    "通信費": (7000, 9000),
    "交通費": (5000, 15000),
    "交際費": (5000, 30000),
    "趣味・娯楽": (3000, 25000),
    "日用品": (4000, 12000),
    "医療費": (0, 8000),
}


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "sample.db"
    rng = random.Random(20260707)

    conn = sqlite3.connect(out)
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.execute("DELETE FROM transactions")

    today = date.today()
    first = date(today.year, today.month, 1) - timedelta(days=420)
    month = date(first.year, first.month, 1)

    rows = []
    while month <= today:
        # 給与(毎月25日)+ たまの副収入
        rows.append((month.replace(day=25).isoformat(), 310000, "income", "給与", "月給"))
        if rng.random() < 0.35:
            d = month.replace(day=rng.randint(5, 20))
            rows.append((d.isoformat(), rng.randint(10000, 60000), "income", "副収入", None))
        if month.month in (6, 12):
            rows.append((month.replace(day=10).isoformat(), 450000, "income", "賞与", "ボーナス"))

        for cat, (lo, hi) in EXPENSE_CATEGORIES.items():
            total = rng.randint(lo, hi) if hi > lo else lo
            if total == 0:
                continue
            # カテゴリごとに数回に分けて記録
            n = 1 if cat in ("住居費", "通信費") else rng.randint(2, 6)
            for _ in range(n):
                d = month.replace(day=rng.randint(1, 28))
                rows.append((d.isoformat(), max(1, total // n), "expense", cat, None))

        month = (month.replace(day=28) + timedelta(days=5)).replace(day=1)

    conn.executemany(
        "INSERT INTO transactions (date, amount, type, category, memo) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"{out} に {len(rows)} 件のトランザクションを生成しました")


if __name__ == "__main__":
    main()
