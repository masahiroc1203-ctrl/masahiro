import re
from typing import Optional

import pdfplumber
from pypdf import PdfReader


def extract_hinmei(pdf_path: str) -> Optional[str]:
    """
    PDFから「品名」フィールドの値を抽出する。
    優先順位:
    1. pypdfでPDFフォームフィールドを確認
    2. pdfplumberで全ページのテーブルを探索
    3. pdfplumberで全ページのテキストからパターンマッチ
    """
    # 1. pypdfでフォームフィールドを確認
    try:
        reader = PdfReader(pdf_path)
        fields = reader.get_fields()
        if fields:
            for field_name, field_value in fields.items():
                if "品名" in field_name:
                    value = field_value.get("/V") if isinstance(field_value, dict) else None
                    if value and isinstance(value, str):
                        stripped = value.strip()
                        if stripped:
                            return stripped
    except Exception:
        pass

    # 2. pdfplumberでテーブルを探索
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row_idx, row in enumerate(table):
                        for col_idx, cell in enumerate(row):
                            if cell and "品名" in str(cell):
                                # 右隣のセルを確認
                                if col_idx + 1 < len(row):
                                    right = row[col_idx + 1]
                                    if right and str(right).strip():
                                        return str(right).strip()
                                # 下のセルを確認
                                if row_idx + 1 < len(table):
                                    next_row = table[row_idx + 1]
                                    if col_idx < len(next_row):
                                        below = next_row[col_idx]
                                        if below and str(below).strip():
                                            return str(below).strip()
    except Exception:
        pass

    # 3. pdfplumberでテキストからパターンマッチ
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pattern = r"品名[：:：\s]*(.+)"
                match = re.search(pattern, text)
                if match:
                    value = match.group(1).strip()
                    if value:
                        return value
    except Exception:
        pass

    return None
