"""温度・電力・ガスの関係を分析し、レポートとグラフを output/ に出力する。

実行: python analyze.py  （data/ に CSV を置いてから）
data/electricity_hourly.csv（HEMS回路別）があれば部屋別分析も行う。
"""

import pandas as pd

from config import (
    CDD_BASE_C,
    COMFORT_MAX_C,
    COMFORT_MIN_C,
    ELECTRICITY_CSV,
    GAS_CSV,
    HDD_BASE_C,
    OUTPUT_DIR,
    REPORT_MD,
    TEMPERATURE_CSV,
)
from plots import (
    plot_daily_overview,
    plot_gas_vs_hdd,
    plot_room_profile,
    plot_room_shares,
    plot_temp_vs_electricity,
)
from regression import linear_fit
from report import format_report
from room_analysis import analyze_rooms, daily_total, load_hourly


def load_daily(elec_daily: pd.DataFrame | None) -> pd.DataFrame:
    """日次の温度・電力データを読み込みマージする。

    elec_daily が渡されたら（時間別データからの集計）それを優先し、
    なければ data/electricity.csv を読む。
    """
    temp = pd.read_csv(TEMPERATURE_CSV, parse_dates=["date"])
    if elec_daily is None:
        elec_daily = pd.read_csv(ELECTRICITY_CSV, parse_dates=["date"])
    df = temp.merge(elec_daily, on="date", how="inner").sort_values("date")
    if df.empty:
        raise ValueError("温度と電力の日付が一致しません。data/ のCSVを確認してください。")
    return df


def load_gas_monthly() -> pd.DataFrame:
    gas = pd.read_csv(GAS_CSV)
    gas["month"] = pd.to_datetime(gas["month"], format="%Y-%m")
    return gas.sort_values("month")


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
    return {
        "comfort_ratio": float(in_band.mean()),
        "cold_days_below_comfort": int((winter["indoor_temp_c"] < COMFORT_MIN_C).sum()),
        "winter_indoor_mean": float(winter["indoor_temp_c"].mean()) if not winter.empty else float("nan"),
        "winter_delta_mean": float((winter["indoor_temp_c"] - winter["outdoor_temp_c"]).mean())
        if not winter.empty
        else float("nan"),
    }


def main() -> None:
    hourly = load_hourly()
    elec_daily = daily_total(hourly) if hourly is not None else None
    daily = load_daily(elec_daily)
    gas_monthly = load_gas_monthly()

    elec = analyze_electricity(daily)
    gas = analyze_gas(gas_monthly, daily)
    comfort = analyze_comfort(daily)
    rooms = analyze_rooms(hourly, daily) if hourly is not None else None

    OUTPUT_DIR.mkdir(exist_ok=True)
    plot_daily_overview(daily)
    plot_temp_vs_electricity(daily, elec)
    plot_gas_vs_hdd(gas["merged"], gas["reg"])
    if rooms:
        plot_room_shares(rooms)
        plot_room_profile(rooms)

    REPORT_MD.write_text(format_report(elec, gas, comfort, rooms), encoding="utf-8")
    print(f"レポートを {REPORT_MD} に出力しました")


if __name__ == "__main__":
    main()
