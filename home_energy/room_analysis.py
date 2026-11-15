"""部屋別・時間別電力データ（HEMS回路別計測）の分析。

data/electricity_hourly.csv（datetime, room, kwh のロング形式）があれば
自動で読み込まれ、部屋別内訳・時間帯プロファイル・部屋別冷房感応度を算出する。
ファイルがなければ日次合計CSVのみで従来分析にフォールバックする。
"""

import pandas as pd

from config import CDD_BASE_C, ELECTRICITY_HOURLY_CSV
from regression import Regression, linear_fit


def load_hourly() -> pd.DataFrame | None:
    """時間別CSVを読み込む。存在しなければ None。"""
    if not ELECTRICITY_HOURLY_CSV.exists():
        return None
    df = pd.read_csv(ELECTRICITY_HOURLY_CSV, parse_dates=["datetime"])
    df["date"] = df["datetime"].dt.normalize()
    df["hour"] = df["datetime"].dt.hour
    return df


def daily_total(hourly: pd.DataFrame) -> pd.DataFrame:
    """時間別データを日次の家全体合計に集計する（従来分析への入力）。"""
    return (
        hourly.groupby("date", as_index=False)["kwh"]
        .sum()
        .rename(columns={"kwh": "electricity_kwh"})
    )


def analyze_rooms(hourly: pd.DataFrame, daily: pd.DataFrame) -> dict:
    """部屋別の年間内訳・平均時間帯プロファイル・冷房感応度を算出する。

    冷房感応度は「外気がCDD基準を超えた日」の部屋別日次kWhを
    (外気温 - 基準) に回帰した傾き。冷房が効きにくい部屋（吹き抜け等）ほど大きく出る。
    """
    shares = hourly.groupby("room")["kwh"].sum().sort_values(ascending=False)

    profile = hourly.groupby(["hour", "room"])["kwh"].mean().unstack("room")

    room_daily = hourly.groupby(["date", "room"], as_index=False)["kwh"].sum()
    merged = room_daily.merge(daily[["date", "outdoor_temp_c"]], on="date", how="inner")
    hot = merged[merged["outdoor_temp_c"] > CDD_BASE_C]

    cooling_regs: dict[str, Regression | None] = {
        room: linear_fit(group["outdoor_temp_c"] - CDD_BASE_C, group["kwh"])
        for room, group in hot.groupby("room")
    }

    return {
        "shares": shares,
        "profile": profile,
        "cooling_regs": cooling_regs,
        "total_kwh": float(shares.sum()),
    }
