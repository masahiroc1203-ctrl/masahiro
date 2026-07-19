"""HEMS計測ユニットの回路別瞬時電力をリアルタイム表示する。

計測チャンネルと実際の回路（部屋・家電）の対応を特定するための調査ツール。
家電を1つずつON/OFFしながら本ツールの表示を見て、値が動いたチャンネルを記録する。

使い方: python watch_channels.py [監視秒数(省略時60)]
依存: 標準ライブラリのみ
"""

import socket
import struct
import sys
import time

from discover_echonet import EHD1, EHD2, ESV_GET, ESV_GET_RES, NODE_PROFILE, parse_response

ECHONET_PORT = 3610  # 計測ユニットは送信元ポート3610宛にしか応答しない
METER_IP = "192.168.11.3"
EOJ_DBOARD = b"\x02\x87\x01"  # 分電盤メータリング
EOJ_PV = b"\x02\x79\x01"  # 住宅用太陽光発電

EPC_MASTER_INSTANT_W = 0xC6  # マスタ瞬時電力（売電時は負）
EPC_CHANNEL_INSTANT_LIST = 0xB7  # 回路別瞬時電力リスト
EPC_PV_INSTANT_W = 0xE0  # 太陽光瞬時発電電力

POLL_INTERVAL_SEC = 3.0
RESPONSE_TIMEOUT_SEC = 2.0
DEFAULT_DURATION_SEC = 60
NO_DATA = 0x7FFE  # ECHONET規定の「計測値なし」


def build_multi_get(tid: int, deoj: bytes, epcs: list[int]) -> bytes:
    body = b"".join(struct.pack(">BB", epc, 0) for epc in epcs)
    return (
        struct.pack(">BBH", EHD1, EHD2, tid)
        + NODE_PROFILE
        + deoj
        + struct.pack(">BB", ESV_GET, len(epcs))
        + body
    )


def get_props(sock: socket.socket, deoj: bytes, epcs: list[int], tid: int) -> dict[int, bytes]:
    sock.sendto(build_multi_get(tid, deoj, epcs), (METER_IP, ECHONET_PORT))
    deadline = time.monotonic() + RESPONSE_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            continue
        if addr[0] != METER_IP:
            continue
        res = parse_response(data)
        if res is None or res["tid"] != tid or res["esv"] != ESV_GET_RES or res["seoj"] != deoj:
            continue
        return res["props"]
    return {}


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
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", ECHONET_PORT))
    sock.settimeout(0.5)

    print(f"回路別瞬時電力を{duration_sec:.0f}秒間監視します（{POLL_INTERVAL_SEC:.0f}秒間隔、Ctrl+Cで中断）")
    header = f"{'時刻':>8} {'マスタW':>8} {'太陽光W':>8} " + " ".join(f"{f'ch{i + 1}':>7}" for i in range(6))
    print(header)

    tid = 0x20
    end = time.monotonic() + duration_sec
    while time.monotonic() < end:
        tid = (tid + 1) & 0xFFFF or 1
        props = get_props(sock, EOJ_DBOARD, [EPC_MASTER_INSTANT_W, EPC_CHANNEL_INSTANT_LIST], tid)
        tid = (tid + 1) & 0xFFFF or 1
        pv_props = get_props(sock, EOJ_PV, [EPC_PV_INSTANT_W], tid)

        master = None
        if len(props.get(EPC_MASTER_INSTANT_W, b"")) == 4:
            master = struct.unpack(">i", props[EPC_MASTER_INSTANT_W])[0]
        pv = None
        if len(pv_props.get(EPC_PV_INSTANT_W, b"")) == 2:
            pv = struct.unpack(">H", pv_props[EPC_PV_INSTANT_W])[0]
        channels = parse_channel_watts(props.get(EPC_CHANNEL_INSTANT_LIST, b""))

        now = time.strftime("%H:%M:%S")
        row = f"{now:>8} {fmt(master, 8)} {fmt(pv, 8)} " + " ".join(fmt(w) for w in channels)
        print(row, flush=True)
        time.sleep(POLL_INTERVAL_SEC)
    sock.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DURATION_SEC
    watch(duration)
