"""分析全体で使う定数。起動後に変わらない値のみ置く（Config/State分離）。"""

from pathlib import Path

# --- パス ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"

TEMPERATURE_CSV = DATA_DIR / "temperature.csv"
ELECTRICITY_CSV = DATA_DIR / "electricity.csv"
GAS_CSV = DATA_DIR / "gas.csv"

REPORT_MD = OUTPUT_DIR / "report.md"

# --- 度日（degree-day）の基準温度 ---
# HDD基準18°C・CDD基準24°Cは日本の住宅エネルギー分析で一般的な値。
# 自宅の暖房開始温度に合わせて調整してよい。
HDD_BASE_C = 18.0
CDD_BASE_C = 24.0

# --- 快適域（室温の評価バンド） ---
COMFORT_MIN_C = 18.0  # WHO推奨の冬季最低室温
COMFORT_MAX_C = 28.0  # 夏季の目安上限

# --- 料金単価（レポートの金額換算用。契約プランに合わせて更新する） ---
ELECTRICITY_YEN_PER_KWH = 31.0  # 中部電力ミライズ従量電灯B 2段目相当の目安
GAS_YEN_PER_M3 = 210.0  # 東邦ガス一般料金の目安

# --- 回帰に必要な最低サンプル数（少なすぎる回帰は誤解を招くため） ---
MIN_REGRESSION_SAMPLES = 5
