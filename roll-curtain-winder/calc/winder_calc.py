#!/usr/bin/env python3
"""ロールカーテン自動巻き取り機（ロール直下・チェーン2本挟み込み式・STS3215）の計算。

使い方:
    python3 winder_calc.py                         # 既定値（推定モデル・STS3215-C001）
    python3 winder_calc.py --servo c046            # 減速比 1:147 版で比較
    python3 winder_calc.py --f-up 22 --travel 1.85 --s-head 18.5
        # 実測値（上げ方向の最大チェーン力[N]、全行程[m]、ヘッドのチェーン間隔の半分[mm]）で再計算
    python3 winder_calc.py --t-bd 0.15             # 実測したサーボ逆駆動トルク[N·m]で手動操作力を計算

標準ライブラリのみで動作する。根拠は docs/mechanical_design.md を参照。
"""
from __future__ import annotations

import argparse
import math

G = 9.80665
KGCM = G / 100.0  # 1 kg·cm = 0.0980665 N·m

# STS3215 の主な版（7.4 V）。C044 はトルク表記が販売店でばらつくため控えめな値を採用
SERVOS = {
    "c001": {"name": "STS3215-C001（1:345）", "stall_kgcm": 19.5, "noload_rpm": 52.0, "ratio": 345},
    "c044": {"name": "STS3215-C044（1:191）", "stall_kgcm": 16.0, "noload_rpm": 86.0, "ratio": 191},
    "c046": {"name": "STS3215-C046（1:147）", "stall_kgcm": 14.4, "noload_rpm": 106.0, "ratio": 147},
}


# ---------------------------------------------------------------- カーテン側
def roll_diameter(x_hang: float, a: argparse.Namespace) -> float:
    """垂れ下がり長さ x_hang[m] のときの巻き径[m]。布を厚さ t のスパイラルとして近似。"""
    wound = a.height - x_hang
    return math.sqrt(a.pipe_d ** 2 + 4.0 * a.cloth_t * wound / math.pi)


def roller_torque(x_hang: float, a: argparse.Namespace) -> float:
    """ローラー軸トルク[N·m]（巻き上げに必要な静的トルク）。"""
    m_cloth = a.cloth_density * a.width * a.height
    m_hang = a.bar_mass + m_cloth * (x_hang / a.height)
    return G * m_hang * roll_diameter(x_hang, a) / 2.0


def chain_profile(a: argparse.Namespace, n: int = 2000):
    """全行程にわたる最大チェーン力[N]とチェーン移動量[m]。"""
    f_max = 0.0
    travel = 0.0
    dx = a.height / n
    for i in range(n + 1):
        x = a.height * i / n
        f_max = max(f_max, roller_torque(x, a) / (a.cw_pcd / 2.0) / a.eta_head)
        if i < n:
            travel += a.cw_pcd / roll_diameter(x + dx / 2.0, a) * dx
    return f_max, travel


# ---------------------------------------------------------------- ユニット側
def sprocket(n_teeth: int, pitch: float):
    """ピッチ円半径[m]・歯先半径[m]・1回転送り[m]。"""
    r = pitch / (2.0 * math.sin(math.pi / n_teeth))
    return r, r + 0.3 * a_ball, n_teeth * pitch


def pinch_geometry(n_teeth: int, a: argparse.Namespace):
    """ピンチローラー配置と巻き掛け角。長さは mm、角度は度。

    チェーンはヘッドのホイールから下りてきてスプロケットの外側に接し、
    角度 gamma の位置にある外側のピンチローラーで向きを戻されて真下に垂れる。
    """
    r, _, _ = sprocket(n_teeth, a.pitch)
    r *= 1e3
    rho = a.brg_od / 2.0 + a.ball_d / 2.0              # ローラー周りのボール中心半径
    d = r + rho + a.pinch_clr                           # スプロケット中心〜ローラー中心
    roll_u = d * math.cos(math.radians(a.gamma))
    leg_u = roll_u - rho                                # ユニット下のチェーン位置（中心から）
    z_head = a.z_top + a.head_gap + a.head_drop        # ヘッドのホイール中心の高さ
    hd = math.hypot(a.s_head, z_head)
    a_in = math.degrees(math.atan2(z_head, a.s_head) - math.acos(r / hd))
    wrap = a.gamma + a_in
    tip = r + 0.3 * a.ball_d
    roll_gap = d - a.brg_od / 2.0 - tip                 # ローラーと歯先のすきま
    return {"r": r, "d": d, "rho": rho, "roll_u": roll_u, "leg_u": leg_u,
            "a_in": a_in, "wrap": wrap, "pockets": wrap / (360.0 / n_teeth), "roll_gap": roll_gap}


def servo_at(torque: float, sv: dict):
    ts = sv["stall_kgcm"] * KGCM
    ratio = torque / ts
    return ratio, sv["noload_rpm"] * max(0.0, 1.0 - ratio)


a_ball = 4.5e-3  # sprocket() の歯先計算用（m）


def main() -> None:
    global a_ball
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # カーテン
    p.add_argument("--width", type=float, default=1.8, help="スクリーン幅 [m]")
    p.add_argument("--height", type=float, default=2.0, help="昇降行程 [m]")
    p.add_argument("--cloth-density", type=float, default=0.35, help="生地の面密度 [kg/m^2]")
    p.add_argument("--cloth-t", type=float, default=0.5e-3, help="生地厚 [m]")
    p.add_argument("--bar-mass", type=float, default=0.4, help="ウエイトバー質量 [kg]")
    p.add_argument("--pipe-d", type=float, default=0.032, help="ローラーパイプ外径 [m]")
    p.add_argument("--cw-pcd", type=float, default=0.038, help="ヘッド側チェーンホイールのピッチ円径 [m]")
    p.add_argument("--eta-head", type=float, default=0.7, help="ヘッド機構の効率")
    p.add_argument("--f-down", type=float, default=8.0, help="下げ方向のチェーン力 [N]")
    p.add_argument("--f-up", type=float, default=None, help="実測: 上げ方向の最大チェーン力 [N]")
    p.add_argument("--travel", type=float, default=None, help="実測: 全行程のチェーン移動量 [m]")
    # ユニット
    p.add_argument("--teeth", type=int, default=14, help="スプロケット歯数")
    p.add_argument("--pitch", type=float, default=6.0e-3, help="ボールチェーンのピッチ [m]")
    p.add_argument("--ball-d", type=float, default=4.5, help="ボール径 [mm]")
    p.add_argument("--s-head", type=float, default=19.0, help="ヘッドから垂れる2本の中心間距離の1/2 [mm]")
    p.add_argument("--head-gap", type=float, default=30.0, help="ユニット上面〜ヘッド下面 [mm]")
    p.add_argument("--head-drop", type=float, default=25.0, help="ヘッド下面〜ヘッドのホイール中心 [mm]")
    p.add_argument("--z-top", type=float, default=20.0, help="スプロケット中心〜ユニット上面 [mm]")
    p.add_argument("--gamma", type=float, default=57.0, help="ピンチローラーの角度 [deg]")
    p.add_argument("--brg-od", type=float, default=6.0, help="ピンチローラー（軸受）外径 [mm]")
    p.add_argument("--pinch-clr", type=float, default=0.2, help="ピンチ部のすきま [mm]")
    p.add_argument("--eta-unit", type=float, default=0.95, help="ユニット内（ローラー・ガイド）の効率")
    # サーボ・設計
    p.add_argument("--servo", choices=sorted(SERVOS), default="c001")
    p.add_argument("--margin", type=float, default=1.4, help="チェーン力の設計余裕")
    p.add_argument("--cont-ratio", type=float, default=0.25, help="連続使用の上限（ストール比）")
    p.add_argument("--speed-ratio", type=float, default=0.80, help="運転速度（負荷時回転数に対する指令比）")
    p.add_argument("--t-bd", type=float, default=None, help="実測: トルクOFF時のサーボ逆駆動トルク [N·m]")
    a = p.parse_args()
    a_ball = a.ball_d * 1e-3
    sv = SERVOS[a.servo]

    f_model, travel_model = chain_profile(a)
    f_up = a.f_up if a.f_up is not None else f_model
    travel = a.travel if a.travel is not None else travel_model
    f_unit = f_up / a.eta_unit
    f_design = f_unit * a.margin
    m_cloth = a.cloth_density * a.width * a.height

    print("## 負荷")
    print()
    print(f"- 吊り下げ最大 {m_cloth + a.bar_mass:.2f} kg（生地 {m_cloth:.2f} + ウエイトバー {a.bar_mass:.2f}）")
    src = "実測" if a.f_up is not None else "推定"
    print(f"- 上げ方向 最大チェーン力 F_up = {f_up:.1f} N（{src}）→ ユニット内損失込み {f_unit:.1f} N")
    print(f"- 設計チェーン力 = {f_unit:.1f} × {a.margin} = {f_design:.1f} N")
    src = "実測" if a.travel is not None else "推定"
    print(f"- 全行程のチェーン移動量 L = {travel:.2f} m（{src}）")
    print()

    print("## 歯数ごとの比較（{}）".format(sv["name"]))
    print()
    print("| 歯数 | PCD [mm] | 巻き掛け [deg] | かみ合い [ポケット] | 設計トルク [kg·cm] | ストール比 | 上げ時間 [s] | ユニット下の2本の間隔 [mm] |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for n in range(12, 19, 2):
        r, _, feed = sprocket(n, a.pitch)
        g = pinch_geometry(n, a)
        t = f_design * r
        ratio, rpm = servo_at(t, sv)
        v = feed * rpm * a.speed_ratio / 60.0
        flag = " ⚠" if ratio > a.cont_ratio else ""
        print(f"| {n} | {2 * r * 1e3:.1f} | {g['wrap']:.0f} | {g['pockets']:.1f} | {t / KGCM:.2f} | "
              f"{ratio * 100:.0f}%{flag} | {travel / v:.0f} | {2 * g['leg_u']:.1f} |")
    print()

    n = a.teeth
    r, tip, feed = sprocket(n, a.pitch)
    g = pinch_geometry(n, a)
    t_up = f_design * r
    ratio, rpm = servo_at(t_up, sv)
    rpm_cmd = rpm * a.speed_ratio
    v = feed * rpm_cmd / 60.0
    sps = rpm_cmd / 60.0 * 4096
    print(f"## 採用案: {n} 歯 + {sv['name']}")
    print()
    print(f"- PCD {2 * r * 1e3:.2f} mm / 1 回転 {feed * 1e3:.0f} mm / 1 step = {feed / 4096 * 1e3:.4f} mm")
    print(f"- ピンチローラー: スプロケット中心から {g['d']:.2f} mm、水平から下 {a.gamma:.0f}°、"
          f"歯先とのすきま {g['roll_gap']:.2f} mm")
    print(f"- 巻き掛け: {g['a_in']:+.1f}° から -{a.gamma:.0f}° まで = {g['wrap']:.1f}°（約 {g['pockets']:.1f} ポケット）")
    print(f"- ユニット下のチェーン: 中心から ±{g['leg_u']:.2f} mm（2 本の間隔 {2 * g['leg_u']:.1f} mm）")
    print(f"- 設計トルク {t_up / KGCM:.2f} kg·cm（ストールの {ratio * 100:.0f}%）")
    print(f"- 指令 {rpm_cmd:.0f} rpm ≒ Goal Speed {sps:.0f} step/s → {v * 1e3:.0f} mm/s、"
          f"全行程 {travel / v:.0f} 秒・{travel / feed:.1f} 回転")
    print()

    print("## 手で引くときの力（トルク OFF、モーターを逆に回しながら引く）")
    print()
    print("F_手 = F_up / η_unit + T_bd / r（T_bd = サーボの逆駆動トルク。実測が必要）")
    print()
    print("| 逆駆動トルク T_bd [N·m] | 上乗せ [N] | 全閉から上げ始めの手の力 [N] | [kgf] |")
    print("|---:|---:|---:|---:|")
    cases = [a.t_bd] if a.t_bd is not None else [0.05, 0.1, 0.2, 0.3]
    for tbd in cases:
        add = tbd / r
        print(f"| {tbd:.2f} | {add:.1f} | {f_unit + add:.1f} | {(f_unit + add) / G:.1f} |")
    print()
    print(f"（参考: ユニットなしの既製品のまま引く力 = {f_up:.1f} N = {f_up / G:.1f} kgf）")


if __name__ == "__main__":
    main()
