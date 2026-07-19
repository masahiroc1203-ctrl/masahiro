"""温度・電力・ガスの関係を分析し、レポートとグラフを output/ に出力する。

実行: python analyze.py  （data/ に CSV を置いてから）
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import (
    CDD_BASE_C,
    COMFORT_MAX_C,
    COMFORT_MIN_C,
    ELECTRICITY_CSV,
    ELECTRICITY_YEN_PER_KWH,
    GAS_CSV,
    GAS_YEN_PER_M3,
    HDD_BASE_C,
    MIN_REGRESSION_SAMPLES,
    OUTPUT_DIR,
    REPORT_MD,
    TEMPERATURE_CSV,
)
from plots import plot_daily_overview, plot_gas_vs_hdd, plot_temp_vs_electricity


@dataclass
class Regression:
    """単回帰の結果。slope=温度感応度、intercept=ベース使用量。"""

    slope: float
    intercept: float
    r2: float
    n: int


def load_daily() -> pd.DataFrame:
    """日次の温度・電力データを読み込みマージする。"""
    temp = pd.read_csv(TEMPERATURE_CSV, parse_dates=["date"])
    elec = pd.read_csv(ELECTRICITY_CSV, parse_dates=["date"])
    df = temp.merge(elec, on="date", how="inner").sort_values("date")
    if df.empty:
        raise ValueError("温度と電力の日付が一致しません。data/ のCSVを確認してください。")
    return df


def load_gas_monthly() -> pd.DataFrame:
    gas = pd.read_csv(GAS_CSV)
    gas["month"] = pd.to_datetime(gas["month"], format="%Y-%m")
    return gas.sort_values("month")


def linear_fit(x: pd.Series, y: pd.Series) -> Regression | None:
    """最小二乗の単回帰。サンプル不足時は None（誤った回帰を出さない）。"""
    mask = x.notna() & y.notna()
    x_v, y_v = x[mask].to_numpy(dtype=float), y[mask].to_numpy(dtype=float)
    if len(x_v) < MIN_REGRESSION_SAMPLES:
        return None
    slope, intercept = np.polyfit(x_v, y_v, 1)
    pred = slope * x_v + intercept
    ss_res = float(np.sum((y_v - pred) ** 2))
    ss_tot = float(np.sum((y_v - y_v.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return Regression(float(slope), float(intercept), r2, len(x_v))


def analyze_electricity(df: pd.DataFrame) -> dict:
    """外気温と電力の関係を暖房域・中間域・冷房域に分けて分析する。"""
    heating = df[df["outdoor_temp_c"] < HDD_BASE_C]
    cooling = df[df["outdoor_temp_c"] > CDD_BASE_C]
    neutral = df[df["outdoor_temp_c"].between(HDD_BASE_C, CDD_BASE_C)]

    heat_reg = linear_fit(HDD_BASE_C - heating["outdoor_temp_c"], heating["electricity_kwh"])
    cool_reg = linear_fit(cooling["outdoor_temp_c"] - CDD_BASE_C, cooling["electricity_kwh"])
    base_kwh = float(neutral["electricity_kwh"].mean()) if not neutral.empty else float("nan")

    total_kwh = float(df["electricity_kwh"].sum())
    base_share = base_kwh * len(df) / total_kwh if total_kwh > 0 else float("nan")

    return {
        "heat_reg": heat_reg,
        "cool_reg": cool_reg,
        "base_kwh": base_kwh,
        "base_share": base_share,
        "total_kwh": total_kwh,
        "corr_temp_elec": float(df["outdoor_temp_c"].corr(df["electricity_kwh"])),
        "n_days": len(df),
    }


def analyze_gas(gas: pd.DataFrame, daily: pd.DataFrame) -> dict:
    """月次ガス使用量を月次HDDに回帰し、ベース（給湯・調理）と暖房分を分離する。"""
    hdd = (
        (HDD_BASE_C - daily["outdoor_temp_c"])
        .clip(lower=0)
        .groupby(daily["date"].dt.to_period("M"))
        .sum()
        .rename("hdd")
        .reset_index()
    )
    hdd["month"] = hdd["date"].dt.to_timestamp()
    merged = gas.merge(hdd[["month", "hdd"]], on="month", how="inner")

    reg = linear_fit(merged["hdd"], merged["gas_m3"])
    return {
        "merged": merged,
        "reg": reg,
        "total_m3": float(gas["gas_m3"].sum()),
        "corr_hdd_gas": float(merged["hdd"].corr(merged["gas_m3"])) if len(merged) > 2 else float("nan"),
    }


def analyze_comfort(df: pd.DataFrame) -> dict:
    """室温が快適域に収まっている割合と、断熱の効き（室内外温度差）を見る。"""
    in_band = df["indoor_temp_c"].between(COMFORT_MIN_C, COMFORT_MAX_C)
    winter = df[df["outdoor_temp_c"] < HDD_BASE_C]
    cold_mornings = int((winter["indoor_temp_c"] < COMFORT_MIN_C).sum())
    return {
        "comfort_ratio": float(in_band.mean()),
        "cold_days_below_comfort": cold_mornings,
        "winter_indoor_mean": float(winter["indoor_temp_c"].mean()) if not winter.empty else float("nan"),
        "winter_delta_mean": float((winter["indoor_temp_c"] - winter["outdoor_temp_c"]).mean())
        if not winter.empty
        else float("nan"),
    }


def build_recommendations(elec: dict, gas: dict, comfort: dict) -> list[str]:
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
    if gas["reg"]:
        heating_m3 = gas["total_m3"] - gas["reg"].intercept * len(gas["merged"])
        if heating_m3 > 0:
            yen = heating_m3 * GAS_YEN_PER_M3
            recs.append(
                f"ガスのうち暖房起因は年間約{heating_m3:.0f} m³（約{yen:,.0f}円）と推定されます。"
                "エアコン暖房（ヒートポンプ）への一部シフトで削減余地があります。"
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


def format_report(elec: dict, gas: dict, comfort: dict) -> str:
    """分析結果をMarkdownレポートにまとめる。"""

    def reg_line(name: str, reg: Regression | None, unit: str) -> str:
        if reg is None:
            return f"- {name}: サンプル不足のため未算出"
        return f"- {name}: **{reg.slope:.2f} {unit}**（R²={reg.r2:.2f}, n={reg.n}）"

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
        reg_line(f"暖房感応度（外気温が{HDD_BASE_C:.0f}°Cを1°C下回るごと）", elec["heat_reg"], "kWh/°C·日"),
        reg_line(f"冷房感応度（外気温が{CDD_BASE_C:.0f}°Cを1°C上回るごと）", elec["cool_reg"], "kWh/°C·日"),
        f"- 年間電力量: {elec['total_kwh']:,.0f} kWh"
        f"（約{elec['total_kwh'] * ELECTRICITY_YEN_PER_KWH:,.0f}円 @ {ELECTRICITY_YEN_PER_KWH:.0f}円/kWh）",
        "",
        "## 2. ガスと暖房度日（HDD）の関係",
        "",
        f"- 月次HDDとの相関係数: {gas['corr_hdd_gas']:.2f}",
        reg_line("HDD感応度", gas["reg"], "m³/HDD"),
    ]
    if gas["reg"]:
        lines.append(
            f"- ベースガス（給湯・調理）: **{gas['reg'].intercept:.1f} m³/月**"
        )
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
        "",
        "## 4. 推奨アクション",
        "",
    ]
    lines += [f"{i}. {r}" for i, r in enumerate(build_recommendations(elec, gas, comfort), 1)]
    lines += [
        "",
        "## グラフ",
        "",
        "![daily overview](daily_overview.png)",
        "![temp vs electricity](temp_vs_electricity.png)",
        "![gas vs hdd](gas_vs_hdd.png)",
        "",
        "---",
        "",
        "> 注: 現在は `generate_sample_data.py` によるサンプルデータでの実行結果です。"
        "実データの入れ方は `home_energy/README.md` を参照。",
    ]
    return "\n".join(lines)


def main() -> None:
    daily = load_daily()
    gas_monthly = load_gas_monthly()

    elec = analyze_electricity(daily)
    gas = analyze_gas(gas_monthly, daily)
    comfort = analyze_comfort(daily)

    OUTPUT_DIR.mkdir(exist_ok=True)
    plot_daily_overview(daily)
    plot_temp_vs_electricity(daily, elec)
    plot_gas_vs_hdd(gas["merged"], gas["reg"])

    REPORT_MD.write_text(format_report(elec, gas, comfort), encoding="utf-8")
    print(f"レポートを {REPORT_MD} に出力しました")


if __name__ == "__main__":
    main()
