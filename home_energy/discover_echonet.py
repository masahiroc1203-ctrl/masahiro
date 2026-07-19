"""ECHONET Lite ノード探索スクリプト。

家庭内LANにマルチキャストで探索パケットを送り、応答したECHONET Lite機器と
そのインスタンス（機器クラス）を一覧表示する。HEMS計測ユニットが
LAN経由で直接ポーリングできるかの事前確認に使う。

使い方: python discover_echonet.py
依存: 標準ライブラリのみ
"""

import socket
import sys
import time

from echonet import (
    ECHONET_PORT,
    ESV_GET_RES,
    ESV_GET_SNA,
    MULTICAST_ADDR,
    NODE_PROFILE,
    build_get_frame,
    get_props,
    open_socket,
    parse_frame,
)

DISCOVERY_TIMEOUT_SEC = 5.0

EPC_INSTANCE_LIST = 0xD6  # 自ノードインスタンスリストS
EPC_GET_PROPERTY_MAP = 0x9F

# 主な機器クラス名（グループコード, クラスコード）
CLASS_NAMES: dict[tuple[int, int], str] = {
    (0x02, 0x87): "分電盤メータリング",
    (0x02, 0x88): "低圧スマート電力量メータ",
    (0x02, 0x79): "住宅用太陽光発電",
    (0x02, 0x7C): "燃料電池",
    (0x02, 0x7D): "蓄電池",
    (0x02, 0x6B): "電気温水器/エコキュート",
    (0x01, 0x30): "家庭用エアコン",
    (0x01, 0x35): "空気清浄器",
    (0x02, 0x90): "一般照明",
    (0x00, 0x11): "温度センサ",
    (0x00, 0x12): "湿度センサ",
    (0x05, 0xFF): "コントローラ",
    (0x0E, 0xF0): "ノードプロファイル",
}


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
    sock = open_socket()
    sock.sendto(build_get_frame(0x0001, NODE_PROFILE, [EPC_INSTANCE_LIST]), (MULTICAST_ADDR, ECHONET_PORT))
    print(f"探索パケット送信 → {MULTICAST_ADDR}:{ECHONET_PORT}（{DISCOVERY_TIMEOUT_SEC}秒待機）")

    nodes: dict[str, list[bytes]] = {}
    deadline = time.monotonic() + DISCOVERY_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            data, addr = sock.recvfrom(1024)
        except socket.timeout:
            continue
        res = parse_frame(data)
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
            props = get_props(sock, ip, eoj, [EPC_GET_PROPERTY_MAP], 0x0002, timeout=3.0)
            epcs = parse_property_map(props.get(EPC_GET_PROPERTY_MAP, b""))
            if epcs:
                print(f"    Get対応EPC: {', '.join(f'0x{e:02X}' for e in epcs)}")
    sock.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    discover()
