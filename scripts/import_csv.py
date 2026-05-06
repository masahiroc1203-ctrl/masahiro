"""
CSVインポートスクリプト
対応フォーマット: 楽天カード, PayPay
使用方法: python import_csv.py --import-dir "C:/expense-import/import"
"""

import argparse
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extras

# --- 接続設定 ---
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "expense",
    "user": "appuser",
    "password": "secret",
}

DEFAULT_USER_NAME = "default"


# --- CSV フォーマット判定 ---

RAKUTEN_HEADERS = {"利用日", "利用店名・商品名", "支払方法", "利用金額"}
PAYPAY_HEADERS  = {"決済日時", "お支払い先", "取引の種類", "金額（税込）"}


def detect_format(headers: list[str]) -> str | None:
    header_set = set(h.strip() for h in headers)
    if RAKUTEN_HEADERS <= header_set:
        return "rakuten"
    if PAYPAY_HEADERS <= header_set:
        return "paypay"
    return None


# --- エンコーディング検出 ---

def read_csv_lines(filepath: Path) -> tuple[list[str], str]:
    for encoding in ("utf-8-sig", "cp932", "utf-8"):
        try:
            text = filepath.read_text(encoding=encoding)
            return text.splitlines(), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f"エンコーディングを判定できません: {filepath}")


# --- 楽天カード パーサー ---

def parse_rakuten(lines: list[str]) -> list[dict]:
    """
    楽天カードCSVから必要行だけ抽出する。
    ヘッダー行を探してから以降のデータ行を読む。
    """
    import csv, io

    header_idx = None
    for i, line in enumerate(lines):
        if "利用日" in line and "利用店名" in line:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("楽天CSVのヘッダー行が見つかりません")

    reader = csv.DictReader(
        io.StringIO("\n".join(lines[header_idx:])),
        skipinitialspace=True,
    )
    records = []
    for row in reader:
        date_str = row.get("利用日", "").strip()
        memo     = row.get("利用店名・商品名", "").strip()
        amount   = row.get("利用金額（円）") or row.get("利用金額", "")
        amount   = amount.replace(",", "").strip()

        if not date_str or not amount:
            continue

        # 日付フォーマット: MM/DD or YYYY/MM/DD or YYYY年MM月DD日
        occurred_at = _parse_date(date_str)
        if occurred_at is None:
            continue

        records.append({
            "occurred_at": occurred_at,
            "memo":        memo,
            "amount":      float(amount),
            "provider":    "楽天カード",
        })
    return records


# --- PayPay パーサー ---

def parse_paypay(lines: list[str]) -> list[dict]:
    import csv, io

    header_idx = None
    for i, line in enumerate(lines):
        if "決済日時" in line and "お支払い先" in line:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("PayPay CSVのヘッダー行が見つかりません")

    reader = csv.DictReader(
        io.StringIO("\n".join(lines[header_idx:])),
        skipinitialspace=True,
    )
    records = []
    for row in reader:
        date_str = row.get("決済日時", "").strip()
        memo     = row.get("お支払い先", "").strip()
        txn_type = row.get("取引の種類", "").strip()
        amount   = (row.get("金額（税込）") or row.get("金額")).replace(",", "").replace("¥", "").replace("－", "-").strip()

        # 「支払い」以外（チャージ、ポイント還元など）はスキップ
        if txn_type and txn_type not in ("支払い", "お支払い"):
            continue
        if not date_str or not amount:
            continue

        occurred_at = _parse_date(date_str)
        if occurred_at is None:
            continue

        records.append({
            "occurred_at": occurred_at,
            "memo":        memo,
            "amount":      abs(float(amount)),
            "provider":    "PayPay",
        })
    return records


# --- 日付パーサー ---

DATE_FORMATS = [
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%m/%d",   # 楽天の月/日形式（年は当年で補完）
]


def _parse_date(s: str) -> datetime | None:
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt
        except ValueError:
            continue
    # 「2024年01月05日」形式
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


# --- DB 挿入 ---

def get_provider_id(cur, name: str) -> int:
    cur.execute("SELECT id FROM providers WHERE name = %s", (name,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"providers に '{name}' が存在しません。02_seed.sql を実行してください。")
    return row[0]


def get_user_id(cur, name: str) -> int:
    cur.execute("SELECT id FROM users WHERE name = %s", (name,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"users に '{name}' が存在しません。02_seed.sql を実行してください。")
    return row[0]


def insert_records(conn, records: list[dict]) -> int:
    inserted = 0
    with conn.cursor() as cur:
        user_id = get_user_id(cur, DEFAULT_USER_NAME)
        provider_cache: dict[str, int] = {}

        for r in records:
            pname = r["provider"]
            if pname not in provider_cache:
                provider_cache[pname] = get_provider_id(cur, pname)

            # 同日・同金額・同メモは重複とみなしてスキップ
            cur.execute(
                """
                SELECT 1 FROM transactions
                WHERE provider_id = %s
                  AND occurred_at = %s
                  AND amount = %s
                  AND memo = %s
                LIMIT 1
                """,
                (provider_cache[pname], r["occurred_at"], r["amount"], r["memo"]),
            )
            if cur.fetchone():
                continue

            cur.execute(
                """
                INSERT INTO transactions
                    (user_id, provider_id, amount, currency, occurred_at, memo)
                VALUES (%s, %s, %s, 'JPY', %s, %s)
                """,
                (user_id, provider_cache[pname], r["amount"], r["occurred_at"], r["memo"]),
            )
            inserted += 1

    conn.commit()
    return inserted


# --- メイン処理 ---

def process_file(filepath: Path, conn) -> tuple[int, str]:
    lines, encoding = read_csv_lines(filepath)
    if not lines:
        return 0, "空ファイル"

    # ヘッダー行を探して判定
    fmt = None
    for line in lines[:20]:
        fmt = detect_format(line.split(","))
        if fmt:
            break

    if fmt is None:
        return 0, f"未対応フォーマット (encoding={encoding})"

    if fmt == "rakuten":
        records = parse_rakuten(lines)
    else:
        records = parse_paypay(lines)

    inserted = insert_records(conn, records)
    return inserted, f"OK ({fmt}, {encoding}, {len(records)}件中{inserted}件挿入)"


def main():
    parser = argparse.ArgumentParser(description="楽天・PayPay CSV インポーター")
    parser.add_argument("--import-dir", default=r"C:\expense-import\import",
                        help="CSVが置かれたフォルダ")
    parser.add_argument("--no-move", action="store_true",
                        help="処理済みファイルを移動しない")
    args = parser.parse_args()

    import_dir = Path(args.import_dir)
    done_dir   = import_dir / "done"
    error_dir  = import_dir / "error"
    done_dir.mkdir(exist_ok=True)
    error_dir.mkdir(exist_ok=True)

    csv_files = list(import_dir.glob("*.csv")) + list(import_dir.glob("*.CSV"))
    if not csv_files:
        print(f"CSVファイルが見つかりません: {import_dir}")
        return

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        for filepath in csv_files:
            try:
                count, status = process_file(filepath, conn)
                print(f"[OK]    {filepath.name}: {status}")
                if not args.no_move:
                    shutil.move(str(filepath), done_dir / filepath.name)
            except Exception as e:
                conn.rollback()
                print(f"[ERROR] {filepath.name}: {e}")
                if not args.no_move:
                    shutil.move(str(filepath), error_dir / filepath.name)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
