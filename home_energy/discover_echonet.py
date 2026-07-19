"""ECHONET Lite ノード探索スクリプト。

家庭内LANにマルチキャストで探索パケットを送り、応答したECHONET Lite機器と
そのインスタンス（機器クラス）を一覧表示する。HEMS計測ユニットが
LAN経由で直接ポーリングできるかの事前確認に使う。

使い方: python discover_echonet.py
依存: 標準ライブラリのみ
"""

import socket
import struct
import sys
import time

ECHONET_PORT = 3610
MULTICAST_ADDR = "224.0.23.0"
DISCOVERY_TIMEOUT_SEC = 5.0
PROPERTY_TIMEOUT_SEC = 3.0

# ECHONET Lite フレームヘッダ
EHD1 = 0x10
EHD2 = 0x81
ESV_GET = 0x62
ESV_GET_RES = 0x72
ESV_GET_SNA = 0x52

# EOJ (ECHONET オブジェクト)
NODE_PROFILE = b"\x0e\xf0\x01"

# EPC
EPC_INSTANCE_LIST = 0xD6  # 自ノードインスタンスリストS
EPC_GET_PROPERTY_MAP = 0x9F

# 主な機器クラス名（グループコード, クラスコード）
CLASS_NAMES: dict[tuple[int, int], str] = {
    (0x02, 0x87): "分電盤メータリング",
    (0x02, 0x88): "低圧スマート電力量メータ",
    (0x02, 0x79): "住宅用太陽光発電",
    (0x02, 0x7D): "蓄電池",
    (0x02, 0x6B): "電気温水器/エコキュート",
    (0x01, 0x30): "家庭用エアコン",
    (0x02, 0x90): "一般照明",
    (0x00, 0x11): "温度センサ",
    (0x00, 0x12): "湿度センサ",
    (0x05, 0xFF): "コントローラ",
    (0x0E, 0xF0): "ノードプロファイル",
}


def build_get_frame(tid: int, deoj: bytes, epc: int) -> bytes:
    """1プロパティのGet要求フレームを組み立てる。"""
    return (
        struct.pack(">BBH", EHD1, EHD2, tid)
        + NODE_PROFILE  # SEOJ: 自分はコントローラ扱いのノードプロファイル
        + deoj
        + struct.pack(">BBBB", ESV_GET, 1, epc, 0)
    )


def parse_response(data: bytes) -> dict | None:
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


def class_label(eoj: bytes) -> str:
    name = CLASS_NAMES.get((eoj[0], eoj[1]), "不明クラス")
    return f"{eoj.hex().upper()} ({name}, インスタンス{eoj[2]})"


def parse_property_map(edt: bytes) -> list[int]:
    """Getプロパティマップ(EPC 0x9F)のEDTをEPCリストに変換する。"""
    if not edt:
        return []
    count = edt[0]
    if count < 16:
        return sorted(edt[1 : 1 + count])
    # 16個以上はビットマップ形式（プロパティ数 + 16バイト）
    epcs: list[int] = []
    for byte_index in range(16):
        if 1 + byte_index >= len(edt):
            break
        bits = edt[1 + byte_index]
        for bit in range(8):
            if bits & (1 << bit):
                epcs.append(0x80 + bit * 0x10 + byte_index)
    return sorted(epcs)


def discover() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", ECHONET_PORT))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    sock.settimeout(0.5)

    frame = build_get_frame(0x0001, NODE_PROFILE, EPC_INSTANCE_LIST)
    sock.sendto(frame, (MULTICAST_ADDR, ECHONET_PORT))
    print(f"探索パケット送信 → {MULTICAST_ADDR}:{ECHONET_PORT}（{DISCOVERY_TIMEOUT_SEC}秒待機）")

    nodes: dict[str, list[bytes]] = {}
    deadline = time.monotonic() + DISCOVERY_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            data, addr = sock.recvfrom(1024)
        except socket.timeout:
            continue
        res = parse_response(data)
        if res is None or res["esv"] not in (ESV_GET_RES, ESV_GET_SNA):
            continue
        edt = res["props"].get(EPC_INSTANCE_LIST, b"")
        if not edt:
            continue
        instances = [edt[1 + i * 3 : 4 + i * 3] for i in range(edt[0])]
        nodes[addr[0]] = instances

    if not nodes:
        print("応答なし。ECHONET Lite機器はこのLANセグメントに見つかりませんでした。")
        print("（計測ユニットが無線接続のみ・別セグメント・電源断の可能性）")
        sock.close()
        return

    for ip, instances in nodes.items():
        print(f"\n■ {ip}")
        for eoj in instances:
            print(f"  - {class_label(eoj)}")
            epcs = get_property_map(sock, ip, eoj)
            if epcs:
                print(f"    Get対応EPC: {', '.join(f'0x{e:02X}' for e in epcs)}")
    sock.close()


def get_property_map(sock: socket.socket, ip: str, eoj: bytes) -> list[int]:
    """対象インスタンスのGetプロパティマップを取得する。"""
    frame = build_get_frame(0x0002, eoj, EPC_GET_PROPERTY_MAP)
    sock.sendto(frame, (ip, ECHONET_PORT))
    deadline = time.monotonic() + PROPERTY_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            data, addr = sock.recvfrom(1024)
        except socket.timeout:
            continue
        if addr[0] != ip:
            continue
        res = parse_response(data)
        if res is None or res["esv"] != ESV_GET_RES or res["seoj"] != eoj:
            continue
        return parse_property_map(res["props"].get(EPC_GET_PROPERTY_MAP, b""))
    return []


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    discover()
