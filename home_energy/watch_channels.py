"""HEMS計測ユニットの回路別瞬時電力をリアルタイム表示する。

計測チャンネルと実際の回路（部屋・家電）の対応を確認するための調査ツール。
家電を1つずつON/OFFしながら本ツールの表示を見て、値が動いたチャンネルを記録する。

使い方: python watch_channels.py [監視秒数(省略時60)]
依存: 標準ライブラリのみ
"""

import struct
import sys
import time

from config import HEMS_CHANNEL_ROOMS, HEMS_METER_IP
from echonet import NO_DATA, get_props, open_socket

EOJ_DBOARD = b"\x02\x87\x01"  # 分電盤メータリング
EOJ_PV = b"\x02\x79\x01"  # 住宅用太陽光発電

EPC_MASTER_INSTANT_W = 0xC6  # マスタ瞬時電力（売電時は負）
EPC_CHANNEL_INSTANT_LIST = 0xB7  # 回路別瞬時電力リスト
EPC_PV_INSTANT_W = 0xE0  # 太陽光瞬時発電電力

POLL_INTERVAL_SEC = 3.0
DEFAULT_DURATION_SEC = 60
CHANNEL_COUNT = len(HEMS_CHANNEL_ROOMS)


def parse_channel_watts(edt: bytes) -> list[int | None]:
    """回路別瞬時電力リスト（先頭2B: 開始ch/ch数、以降4B×ch）をW値リストへ。"""
    if len(edt) < 2:
        return []
    count = edt[1]
    watts: list[int | None] = []
    for i in range(count):
        chunk = edt[2 + i * 4 : 6 + i * 4]
        if len(chunk) < 4:
            break
        value = struct.unpack(">i", chunk)[0]
        watts.append(None if value == NO_DATA else value)
    return watts


def fmt(value: int | None, width: int = 7) -> str:
    return f"{'---':>{width}}" if value is None else f"{value:>{width}}"


def watch(duration_sec: float) -> None:
    sock = open_socket()
    print(f"回路別瞬時電力を{duration_sec:.0f}秒間監視します（{POLL_INTERVAL_SEC:.0f}秒間隔、Ctrl+Cで中断）")
    labels = [HEMS_CHANNEL_ROOMS[ch][:7] for ch in sorted(HEMS_CHANNEL_ROOMS)]
    header = f"{'時刻':>8} {'マスタW':>8} {'太陽光W':>8} " + " ".join(f"{label:>7}" for label in labels)
    print(header)

    tid = 0x20
    end = time.monotonic() + duration_sec
    while time.monotonic() < end:
        tid = (tid + 1) & 0xFFFF or 1
        props = get_props(sock, HEMS_METER_IP, EOJ_DBOARD, [EPC_MASTER_INSTANT_W, EPC_CHANNEL_INSTANT_LIST], tid)
        tid = (tid + 1) & 0xFFFF or 1
        pv_props = get_props(sock, HEMS_METER_IP, EOJ_PV, [EPC_PV_INSTANT_W], tid)

        master = None
        if len(props.get(EPC_MASTER_INSTANT_W, b"")) == 4:
            master = struct.unpack(">i", props[EPC_MASTER_INSTANT_W])[0]
        pv = None
        if len(pv_props.get(EPC_PV_INSTANT_W, b"")) == 2:
            pv = struct.unpack(">H", pv_props[EPC_PV_INSTANT_W])[0]
        channels = parse_channel_watts(props.get(EPC_CHANNEL_INSTANT_LIST, b""))
        channels += [None] * (CHANNEL_COUNT - len(channels))

        now = time.strftime("%H:%M:%S")
        print(f"{now:>8} {fmt(master, 8)} {fmt(pv, 8)} " + " ".join(fmt(w) for w in channels), flush=True)
        time.sleep(POLL_INTERVAL_SEC)
    sock.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DURATION_SEC
    watch(duration)
