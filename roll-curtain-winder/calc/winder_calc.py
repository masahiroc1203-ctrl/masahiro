#!/usr/bin/env python3
"""ロールカーテン自動巻き取り機（チェーン駆動・STS3215）の負荷／トルク／速度計算。

使い方:
    python3 winder_calc.py                 # 既定値（推定モデル）で計算
    python3 winder_calc.py --teeth 12      # スプロケット歯数を指定して詳細表示
    python3 winder_calc.py --f-up 22 --travel 1.85
        # 実測値（上げ方向の最大チェーン力[N]、全行程のチェーン移動量[m]）で上書き

標準ライブラリのみで動作する。数値の根拠は docs/mechanical_design.md の「3. 負荷計算」を参照。
"""
from __future__ import annotations

import argparse
import math

G = 9.80665
KGCM = G / 100.0  # 1 kg·cm = 0.0980665 N·m


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
    """全行程にわたるチェーン力とチェーン移動量を数値積分で求める。"""
    f_max = 0.0
    travel = 0.0
    dx = a.height / n
    for i in range(n + 1):
        x = a.height * i / n
        f = roller_torque(x, a) / (a.cw_pcd / 2.0) / a.eta_head
        f_max = max(f_max, f)
        if i < n:
            xm = x + dx / 2.0
            travel += a.cw_pcd / roll_diameter(xm, a) * dx
    return f_max, travel


def sprocket(n_teeth: int, pitch: float):
    """ボールチェーン用スプロケットのピッチ円直径[m]と1回転あたり送り量[m]。"""
    pcd = pitch / math.sin(math.pi / n_teeth)
    return pcd, n_teeth * pitch


def servo_at(torque: float, a: argparse.Namespace):
    """直線トルク-速度特性で負荷時回転数[rpm]を推定。"""
    ts = a.stall_kgcm * KGCM
    ratio = torque / ts
    rpm = a.noload_rpm * max(0.0, 1.0 - ratio)
    return ratio, rpm


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # カーテン
    p.add_argument("--width", type=float, default=1.8, help="スクリーン幅 [m]")
    p.add_argument("--height", type=float, default=2.0, help="昇降行程（スクリーン高さ）[m]")
    p.add_argument("--cloth-density", type=float, default=0.35, help="生地の面密度 [kg/m^2]（遮光生地 0.3〜0.45）")
    p.add_argument("--cloth-t", type=float, default=0.5e-3, help="生地厚 [m]")
    p.add_argument("--bar-mass", type=float, default=0.4, help="ウエイトバー質量 [kg]")
    # ヘッド（既製ロールスクリーンのチェーン機構）
    p.add_argument("--pipe-d", type=float, default=0.032, help="ローラーパイプ外径 [m]（要実測）")
    p.add_argument("--cw-pcd", type=float, default=0.038, help="ヘッド側チェーンホイールのピッチ円径 [m]（要実測）")
    p.add_argument("--eta-head", type=float, default=0.7, help="ヘッド機構（クラッチ/ブレーキ）の効率")
    p.add_argument("--f-down", type=float, default=8.0, help="下げ方向に必要なチェーン力 [N]（要実測）")
    # 実測値で上書き
    p.add_argument("--f-up", type=float, default=None, help="実測: 上げ方向の最大チェーン力 [N]")
    p.add_argument("--travel", type=float, default=None, help="実測: 全行程のチェーン移動量 [m]")
    # 設計
    p.add_argument("--margin", type=float, default=1.4, help="チェーン力の設計余裕（倍率）")
    p.add_argument("--pitch", type=float, default=6.0e-3, help="ボールチェーンのピッチ [m]")
    p.add_argument("--teeth", type=int, default=14, help="詳細表示するスプロケット歯数")
    # サーボ（STS3215-C001 7.4V, 1:345）
    p.add_argument("--stall-kgcm", type=float, default=19.5, help="ストールトルク [kg·cm] @7.4V")
    p.add_argument("--noload-rpm", type=float, default=52.0, help="無負荷回転数 [rpm] @7.4V")
    p.add_argument("--cont-ratio", type=float, default=0.25, help="連続使用の上限（ストール比）")
    p.add_argument("--speed-ratio", type=float, default=0.80, help="運転速度（負荷時回転数に対する指令比）")
    a = p.parse_args()

    f_model, travel_model = chain_profile(a)
    f_up = a.f_up if a.f_up is not None else f_model
    travel = a.travel if a.travel is not None else travel_model
    f_design = f_up * a.margin
    m_cloth = a.cloth_density * a.width * a.height

    print("## 入力と負荷")
    print()
    print(f"- 生地質量 {m_cloth:.2f} kg + ウエイトバー {a.bar_mass:.2f} kg = 吊り下げ最大 {m_cloth + a.bar_mass:.2f} kg")
    print(f"- 巻き径: 全閉時 {roll_diameter(a.height, a) * 1e3:.1f} mm → 全開時 {roll_diameter(0.0, a) * 1e3:.1f} mm")
    src = "実測" if a.f_up is not None else "推定"
    print(f"- 上げ方向 最大チェーン力 F_up = {f_up:.1f} N（{src}、全閉位置からの巻き上げ開始時）")
    print(f"- 設計チェーン力 F_design = F_up × {a.margin} = {f_design:.1f} N")
    print(f"- 下げ方向 チェーン力 F_down = {a.f_down:.1f} N（仮定）")
    src = "実測" if a.travel is not None else "推定"
    print(f"- 全行程のチェーン移動量 L = {travel:.2f} m（{src}）")
    print()

    print("## スプロケット歯数ごとの比較（ピッチ {:.1f} mm）".format(a.pitch * 1e3))
    print()
    print("| 歯数 | PCD [mm] | 送り [mm/rev] | 設計トルク [kg·cm] | ストール比 | 負荷時 [rpm] | 上げ時間 [s] | 行程の回転数 |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for n in range(10, 21, 2):
        pcd, feed = sprocket(n, a.pitch)
        t = f_design * pcd / 2.0
        ratio, rpm = servo_at(t, a)
        v = feed * rpm * a.speed_ratio / 60.0
        time_up = travel / v if v > 0 else float("inf")
        flag = " ⚠" if ratio > a.cont_ratio else ""
        print(f"| {n} | {pcd * 1e3:.1f} | {feed * 1e3:.0f} | {t / KGCM:.2f} | {ratio * 100:.0f}%{flag} | "
              f"{rpm:.0f} | {time_up:.0f} | {travel / feed:.1f} |")
    print()
    print(f"⚠ = 連続使用の目安（ストールの {a.cont_ratio * 100:.0f}%）を超える")
    print()

    n = a.teeth
    pcd, feed = sprocket(n, a.pitch)
    t_up = f_design * pcd / 2.0
    t_dn = a.f_down * a.margin * pcd / 2.0
    ratio, rpm = servo_at(t_up, a)
    rpm_cmd = rpm * a.speed_ratio
    v = feed * rpm_cmd / 60.0
    steps_per_s = rpm_cmd / 60.0 * 4096
    print(f"## 採用案: {n}歯スプロケット")
    print()
    print(f"- PCD {pcd * 1e3:.2f} mm / 1回転送り {feed * 1e3:.0f} mm / エンコーダ 1step = {feed / 4096 * 1e3:.4f} mm")
    print(f"- 上げ: 設計トルク {t_up / KGCM:.2f} kg·cm（{t_up:.3f} N·m, ストールの {ratio * 100:.0f}%）")
    print(f"- 下げ: 設計トルク {t_dn / KGCM:.2f} kg·cm")
    print(f"- 運転指令 {rpm_cmd:.0f} rpm ≒ {steps_per_s:.0f} step/s（Goal Speed）→ チェーン速度 {v * 1e3:.0f} mm/s")
    print(f"- 全行程 {travel:.2f} m: {travel / v:.0f} 秒, サーボ {travel / feed:.1f} 回転 = {travel / feed * 4096:.0f} step")
    # 開ループ PWM モード（Mode 2）ではロック時トルク ≒ デューティ × ストールトルク
    t_nom = f_up * pcd / 2.0
    for duty in (30, 35, 40):
        f_lim = a.stall_kgcm * KGCM * duty / 100.0 / (pcd / 2.0)
        spd = max(0.0, duty / 100.0 - t_nom / (a.stall_kgcm * KGCM)) * a.noload_rpm
        t_home = travel / (feed * spd / 60.0) if spd > 0 else float("inf")
        print(f"- PWM デューティ {duty}%（Mode 2）: ロック時の最大チェーン力 {f_lim:.0f} N, "
              f"全閉からの原点出し {spd:.0f} rpm・最長 {t_home:.0f} 秒")
    print(f"- 50 Hz ポーリング時の1周期移動量: {steps_per_s / 50:.0f} step（< 2048 なので多回転の展開が可能）")


if __name__ == "__main__":
    main()
