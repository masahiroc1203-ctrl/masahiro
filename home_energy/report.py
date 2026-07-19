"""分析結果をMarkdownレポートに整形する。"""

import numpy as np

from config import (
    CDD_BASE_C,
    COMFORT_MAX_C,
    COMFORT_MIN_C,
    ELECTRICITY_YEN_PER_KWH,
    GAS_YEN_PER_M3,
    HDD_BASE_C,
)
from regression import Regression


def _reg_line(name: str, reg: Regression | None, unit: str) -> str:
    if reg is None:
        return f"- {name}: サンプル不足のため未算出"
    return f"- {name}: **{reg.slope:.2f} {unit}**（R²={reg.r2:.2f}, n={reg.n}）"


def _top_cooling_room(rooms: dict) -> tuple[str, Regression] | None:
    """冷房感応度が最大の部屋を返す。回帰が1つもなければ None。"""
    valid = {r: reg for r, reg in rooms["cooling_regs"].items() if reg is not None}
    if not valid:
        return None
    room = max(valid, key=lambda r: valid[r].slope)
    return room, valid[room]


def build_recommendations(elec: dict, gas: dict, comfort: dict, rooms: dict | None) -> list[str]:
    """分析値から具体的な改善アクションを組み立てる。"""
    recs: list[str] = []

    if not np.isnan(elec["base_share"]) and elec["base_share"] > 0.5:
        recs.append(
            f"ベース電力（空調に依らない待機・常時消費）が全体の約{elec['base_share']:.0%}を占めています。"
            "冷蔵庫の設定・待機電力・照明のLED化など、空調以外の見直しが最も効きます。"
        )
    if elec["heat_reg"] and elec["cool_reg"] and elec["heat_reg"].slope > elec["cool_reg"].slope:
        recs.append(
            f"暖房の温度感応度（{elec['heat_reg'].slope:.2f} kWh/°C·日）が冷房"
            f"（{elec['cool_reg'].slope:.2f} kWh/°C·日）より大きく、冬の断熱・気密改善"
            "（窓の内窓化・隙間対策）の費用対効果が高い状態です。"
        )
    if elec["cool_reg"] and elec["heat_reg"] and elec["cool_reg"].slope >= elec["heat_reg"].slope:
        recs.append(
            f"冷房の温度感応度（{elec['cool_reg'].slope:.2f} kWh/°C·日）が大きめです。"
            "日射遮蔽（すだれ・遮熱カーテン）とエアコンのフィルター清掃が有効です。"
        )
    if rooms:
        top = _top_cooling_room(rooms)
        if top:
            room, reg = top
            advice = (
                "吹き抜けのリビングは冷気が2Fへ逃げやすいため、シーリングファンの下向き運転や"
                "サーキュレーターでの攪拌、日射遮蔽が特に効きます。"
                if "ldk" in room.lower() or "リビング" in room
                else "設定温度の見直し・タイマー運転・フィルター清掃を優先してください。"
            )
            recs.append(
                f"冷房の温度感応度が最も高いのは「{room}」（{reg.slope:.2f} kWh/°C·日）です。{advice}"
            )
    if gas["reg"]:
        heating_m3 = gas["total_m3"] - gas["reg"].intercept * len(gas["merged"])
        if heating_m3 > 0:
            yen = heating_m3 * GAS_YEN_PER_M3
            recs.append(
                f"ガスのうち暖房（床暖房）起因は年間約{heating_m3:.0f} m³（約{yen:,.0f}円）と推定されます。"
                "床暖房は立ち上げ時の消費が大きいため、こまめなON/OFFより低温連続運転が有利です。"
                "外気が緩い日はエアコン暖房（ヒートポンプ）併用も削減余地があります。"
            )
    if comfort["comfort_ratio"] < 0.8:
        recs.append(
            f"室温が快適域（{COMFORT_MIN_C:.0f}–{COMFORT_MAX_C:.0f}°C）にある時間は"
            f"約{comfort['comfort_ratio']:.0%}に留まります。健康面（WHOは冬季18°C以上を推奨）"
            "からも、省エネより先に最低室温の底上げを優先してください。"
        )
    if not recs:
        recs.append("大きな非効率は検出されませんでした。現状の運用を維持しつつ季節ごとに再分析を推奨します。")
    return recs


def format_report(elec: dict, gas: dict, comfort: dict, rooms: dict | None) -> str:
    lines = [
        "# 住環境エネルギー分析レポート",
        "",
        f"対象期間: {elec['n_days']}日分の日次データ",
        "",
        "## 1. 電力と気温の関係",
        "",
        f"- 外気温との相関係数: {elec['corr_temp_elec']:.2f}",
        f"- ベース電力（中間期 {HDD_BASE_C:.0f}–{CDD_BASE_C:.0f}°C の平均）: "
        f"**{elec['base_kwh']:.1f} kWh/日**（全消費の約{elec['base_share']:.0%}）",
        _reg_line(f"暖房感応度（外気温が{HDD_BASE_C:.0f}°Cを1°C下回るごと）", elec["heat_reg"], "kWh/°C·日"),
        _reg_line(f"冷房感応度（外気温が{CDD_BASE_C:.0f}°Cを1°C上回るごと）", elec["cool_reg"], "kWh/°C·日"),
        f"- 年間電力量: {elec['total_kwh']:,.0f} kWh"
        f"（約{elec['total_kwh'] * ELECTRICITY_YEN_PER_KWH:,.0f}円 @ {ELECTRICITY_YEN_PER_KWH:.0f}円/kWh）",
        "",
        "## 2. ガスと暖房度日（HDD）の関係",
        "",
        f"- 月次HDDとの相関係数: {gas['corr_hdd_gas']:.2f}",
        _reg_line("HDD感応度", gas["reg"], "m³/HDD"),
    ]
    if gas["reg"]:
        lines.append(f"- ベースガス（給湯・調理）: **{gas['reg'].intercept:.1f} m³/月**")
    lines += [
        f"- 年間ガス使用量: {gas['total_m3']:,.0f} m³"
        f"（約{gas['total_m3'] * GAS_YEN_PER_M3:,.0f}円 @ {GAS_YEN_PER_M3:.0f}円/m³）",
        "",
        "## 3. 快適性（室温）",
        "",
        f"- 快適域（{COMFORT_MIN_C:.0f}–{COMFORT_MAX_C:.0f}°C）滞在率: {comfort['comfort_ratio']:.0%}",
        f"- 冬季（外気<{HDD_BASE_C:.0f}°C）の平均室温: {comfort['winter_indoor_mean']:.1f}°C",
        f"- 冬季の室内外温度差の平均: {comfort['winter_delta_mean']:.1f}°C（大きいほど断熱・暖房が効いている）",
        f"- 冬季に室温が{COMFORT_MIN_C:.0f}°Cを下回った日数: {comfort['cold_days_below_comfort']}日",
    ]

    if rooms:
        lines += [
            "",
            "## 4. 部屋別分析（HEMS回路別データ）",
            "",
            "| 部屋 | 年間kWh | 構成比 |",
            "| --- | ---: | ---: |",
        ]
        for room, kwh in rooms["shares"].items():
            lines.append(f"| {room} | {kwh:,.0f} | {kwh / rooms['total_kwh']:.0%} |")
        lines += ["", "部屋別の冷房感応度（外気24°C超の日、外気温1°Cあたりの増加量）:", ""]
        for room, reg in sorted(
            rooms["cooling_regs"].items(),
            key=lambda kv: -(kv[1].slope if kv[1] else float("-inf")),
        ):
            lines.append(_reg_line(room, reg, "kWh/°C·日"))

    lines += [
        "",
        "## 推奨アクション",
        "",
    ]
    lines += [f"{i}. {r}" for i, r in enumerate(build_recommendations(elec, gas, comfort, rooms), 1)]
    lines += [
        "",
        "## グラフ",
        "",
        "![daily overview](daily_overview.png)",
        "![temp vs electricity](temp_vs_electricity.png)",
        "![gas vs hdd](gas_vs_hdd.png)",
    ]
    if rooms:
        lines += [
            "![room shares](room_shares.png)",
            "![room profile](room_profile.png)",
        ]
    lines += [
        "",
        "---",
        "",
        "> 注: 現在は `generate_sample_data.py` によるサンプルデータでの実行結果です。"
        "実データの入れ方は `home_energy/README.md` を参照。",
    ]
    return "\n".join(lines)
