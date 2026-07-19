"""分析全体で使う定数。起動後に変わらない値のみ置く（Config/State分離）。"""

from pathlib import Path

# --- パス ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"

TEMPERATURE_CSV = DATA_DIR / "temperature.csv"
ELECTRICITY_CSV = DATA_DIR / "electricity.csv"
ELECTRICITY_HOURLY_CSV = DATA_DIR / "electricity_hourly.csv"  # HEMS回路別（あれば優先）
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

# --- HEMS（NEC IG1002STC/SF 計測ユニット。ECHONET LiteでLAN直接取得） ---
HEMS_METER_IP = "192.168.11.3"
HEMS_RAW_CSV = DATA_DIR / "hems_raw.csv"  # poll_hems.py が積算カウンタを追記する生ログ

# 計測ユニット設定画面（センサ番号→計測対象名）の割り付け。グラフは英語ラベル。
# ch4「エアコン」はLDKエアコンとみられるが未確定（ON/OFFテストで要確認）
HEMS_CHANNEL_ROOMS = {
    1: "Kitchen",  # キッチン
    2: "Living",  # リビング
    3: "BedroomAC",  # 寝室AC
    4: "Aircon",  # エアコン（LDK?）
    5: "Dishwasher",  # 食洗機
    6: "Microwave",  # 電子レンジ
}
HEMS_OTHER_ROOM = "Other"  # マスタ−6ch合計の残り（計測外回路）

# 積算カウンタ→kWh換算。EPC 0xC2=0x03（単位0.001kWh=1Wh/カウント）に基づく暫定値。
# 実データ蓄積後にカテエネ等の実測と突き合わせて検証する。
HEMS_KWH_PER_COUNT = 0.001
