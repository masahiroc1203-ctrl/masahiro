"""HEMS計測ユニットから積算電力量カウンタを読み取り data/hems_raw.csv に追記する。

1回実行で1行追記（タスクスケジューラでの定期実行を想定）。
--interval N を付けるとN秒間隔で回り続ける（PC常駐運用）。
蓄積した生ログは hems_to_hourly.py で electricity_hourly.csv に変換する。

使い方:
  python poll_hems.py              # 1回だけ記録
  python poll_hems.py --interval 300  # 5分間隔で記録し続ける
"""

import argparse
import csv
import struct
import sys
import time
from datetime import datetime

from config import HEMS_METER_IP, HEMS_RAW_CSV
from echonet import get_props, open_socket

EOJ_DBOARD = b"\x02\x87\x01"  # 分電盤メータリング
EOJ_PV = b"\x02\x79\x01"  # 住宅用太陽光発電

# マスタCTは主幹＝系統との潮流を測る。0xC0は買電のみ増え、余剰売電中は停止する（実測確認）
EPC_MASTER_CUMULATIVE = 0xC0  # マスタ積算電力量（正方向＝買電）
EPC_EXPORT_CUMULATIVE = 0xC1  # マスタ積算電力量（逆方向＝売電）
EPC_CHANNEL_CUMULATIVE_LIST = 0xB3  # 回路別積算電力量リスト
EPC_PV_CUMULATIVE = 0xE1  # 太陽光積算発電電力量

CHANNEL_COUNT = 6
CSV_HEADER = ["timestamp", "master", "export", "ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "pv"]
RETRY_COUNT = 3


def parse_channel_list(edt: bytes) -> list[int | None]:
    """回路別リスト（先頭2B: 開始ch/ch数、以降4B×ch）を数値リストへ。"""
    if len(edt) < 2:
        return []
    count = edt[1]
    values: list[int | None] = []
    for i in range(count):
        chunk = edt[2 + i * 4 : 6 + i * 4]
        if len(chunk) < 4:
            break
        values.append(struct.unpack(">I", chunk)[0])
    return values


def read_counters(tid: int) -> dict[str, int | None] | None:
    """全積算カウンタを読み取る。計測ユニット無応答なら None。"""
    sock = open_socket()
    try:
        props = get_props(
            sock,
            HEMS_METER_IP,
            EOJ_DBOARD,
            [EPC_MASTER_CUMULATIVE, EPC_EXPORT_CUMULATIVE, EPC_CHANNEL_CUMULATIVE_LIST],
            tid,
        )
        if not props:
            return None
        pv_props = get_props(sock, HEMS_METER_IP, EOJ_PV, [EPC_PV_CUMULATIVE], tid + 1)
    finally:
        sock.close()

    row: dict[str, int | None] = {}
    master_edt = props.get(EPC_MASTER_CUMULATIVE, b"")
    row["master"] = struct.unpack(">I", master_edt)[0] if len(master_edt) == 4 else None
    export_edt = props.get(EPC_EXPORT_CUMULATIVE, b"")
    row["export"] = struct.unpack(">I", export_edt)[0] if len(export_edt) == 4 else None

    channels = parse_channel_list(props.get(EPC_CHANNEL_CUMULATIVE_LIST, b""))
    for i in range(CHANNEL_COUNT):
        row[f"ch{i + 1}"] = channels[i] if i < len(channels) else None

    pv_edt = pv_props.get(EPC_PV_CUMULATIVE, b"")
    row["pv"] = struct.unpack(">I", pv_edt)[0] if len(pv_edt) == 4 else None
    return row


def append_sample(tid: int) -> bool:
    """1サンプル読み取ってCSVに追記する。成功したらTrue。"""
    row = None
    for _ in range(RETRY_COUNT):
        row = read_counters(tid)
        if row is not None:
            break
        time.sleep(1.0)
    if row is None:
        print("計測ユニットから応答がありません", file=sys.stderr)
        return False

    HEMS_RAW_CSV.parent.mkdir(exist_ok=True)
    is_new = not HEMS_RAW_CSV.exists()
    with HEMS_RAW_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(CSV_HEADER)
        timestamp = datetime.now().isoformat(timespec="seconds")
        writer.writerow([timestamp] + [row[k] if row[k] is not None else "" for k in CSV_HEADER[1:]])
    print(
        f"{timestamp} 記録: 買電={row['master']} 売電={row['export']} "
        f"ch={[row[f'ch{i + 1}'] for i in range(CHANNEL_COUNT)]} pv={row['pv']}"
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="HEMS積算カウンタの記録")
    parser.add_argument("--interval", type=float, default=None, help="秒間隔で連続記録（省略時1回のみ）")
    args = parser.parse_args()

    tid = int(time.time()) & 0x7FFF or 1
    if args.interval is None:
        sys.exit(0 if append_sample(tid) else 1)
    while True:
        append_sample(tid)
        tid = (tid + 2) & 0xFFFF or 1
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
