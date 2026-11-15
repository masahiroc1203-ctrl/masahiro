"""ECHONET Lite 通信の共通ユーティリティ。

discover_echonet.py（探索）・watch_channels.py（監視）・poll_hems.py（収集）で共用する。
依存: 標準ライブラリのみ
"""

import socket
import struct
import time

ECHONET_PORT = 3610  # 計測ユニットは送信元ポート3610宛にしか応答しない（実測）
MULTICAST_ADDR = "224.0.23.0"

# フレームヘッダ
EHD1 = 0x10
EHD2 = 0x81
ESV_GET = 0x62
ESV_GET_RES = 0x72
ESV_GET_SNA = 0x52

NODE_PROFILE = b"\x0e\xf0\x01"
NO_DATA = 0x7FFE  # ECHONET規定の「計測値なし」

DEFAULT_RESPONSE_TIMEOUT_SEC = 2.0


def open_socket(timeout: float = 0.5) -> socket.socket:
    """ポート3610にバインドした送受信用UDPソケットを開く。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", ECHONET_PORT))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    sock.settimeout(timeout)
    return sock


def build_get_frame(tid: int, deoj: bytes, epcs: list[int]) -> bytes:
    """複数EPCのGet要求フレームを組み立てる。"""
    body = b"".join(struct.pack(">BB", epc, 0) for epc in epcs)
    return (
        struct.pack(">BBH", EHD1, EHD2, tid)
        + NODE_PROFILE  # SEOJ: コントローラ側ノードプロファイル
        + deoj
        + struct.pack(">BB", ESV_GET, len(epcs))
        + body
    )


def parse_frame(data: bytes) -> dict | None:
    """応答フレームを解析して {tid, seoj, esv, props: {epc: edt}} を返す。"""
    if len(data) < 12 or data[0] != EHD1 or data[1] != EHD2:
        return None
    tid = struct.unpack(">H", data[2:4])[0]
    seoj = data[4:7]
    esv = data[10]
    opc = data[11]
    props: dict[int, bytes] = {}
    pos = 12
    for _ in range(opc):
        if pos + 2 > len(data):
            break
        epc = data[pos]
        pdc = data[pos + 1]
        props[epc] = data[pos + 2 : pos + 2 + pdc]
        pos += 2 + pdc
    return {"tid": tid, "seoj": seoj, "esv": esv, "props": props}


def get_props(
    sock: socket.socket,
    ip: str,
    deoj: bytes,
    epcs: list[int],
    tid: int,
    timeout: float = DEFAULT_RESPONSE_TIMEOUT_SEC,
) -> dict[int, bytes]:
    """指定機器へGetを送り、応答プロパティを返す（無応答なら空dict）。"""
    sock.sendto(build_get_frame(tid, deoj, epcs), (ip, ECHONET_PORT))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            continue
        res = parse_frame(data)
        if res is None or addr[0] != ip:
            continue
        if res["tid"] != tid or res["esv"] != ESV_GET_RES or res["seoj"] != deoj:
            continue
        return res["props"]
    return {}
