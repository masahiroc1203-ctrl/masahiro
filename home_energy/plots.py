"""グラフ出力。ラベルは英語表記（実行環境に日本語フォントがない場合の文字化け対策）。"""

from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")  # ヘッドレス環境（CI・リモート実行）でも描画できるように
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import CDD_BASE_C, HDD_BASE_C, OUTPUT_DIR

if TYPE_CHECKING:
    from analyze import Regression

FIG_DPI = 120


def plot_daily_overview(df: pd.DataFrame) -> None:
    """温度と電力の時系列を上下2段で並べる。"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True)

    ax1.plot(df["date"], df["outdoor_temp_c"], label="Outdoor", color="tab:blue", lw=0.9)
    ax1.plot(df["date"], df["indoor_temp_c"], label="Indoor", color="tab:orange", lw=0.9)
    ax1.set_ylabel("Temperature (deg C)")
    ax1.legend(loc="upper right")
    ax1.grid(alpha=0.3)

    ax2.plot(df["date"], df["electricity_kwh"], color="tab:green", lw=0.9)
    ax2.set_ylabel("Electricity (kWh/day)")
    ax2.grid(alpha=0.3)

    fig.suptitle("Daily temperature and electricity")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "daily_overview.png", dpi=FIG_DPI)
    plt.close(fig)


def plot_temp_vs_electricity(df: pd.DataFrame, elec: dict) -> None:
    """外気温 vs 電力の散布図。暖房・冷房の回帰線を重ねる。"""
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(df["outdoor_temp_c"], df["electricity_kwh"], s=10, alpha=0.5, color="tab:gray")

    heat_reg: "Regression | None" = elec["heat_reg"]
    cool_reg: "Regression | None" = elec["cool_reg"]

    if heat_reg:
        x = np.linspace(df["outdoor_temp_c"].min(), HDD_BASE_C, 50)
        ax.plot(x, heat_reg.slope * (HDD_BASE_C - x) + heat_reg.intercept, color="tab:red",
                label=f"Heating: {heat_reg.slope:.2f} kWh/degC")
    if cool_reg:
        x = np.linspace(CDD_BASE_C, df["outdoor_temp_c"].max(), 50)
        ax.plot(x, cool_reg.slope * (x - CDD_BASE_C) + cool_reg.intercept, color="tab:blue",
                label=f"Cooling: {cool_reg.slope:.2f} kWh/degC")

    ax.axvspan(HDD_BASE_C, CDD_BASE_C, color="tab:green", alpha=0.08, label="Neutral zone")
    ax.set_xlabel("Outdoor temperature (deg C)")
    ax.set_ylabel("Electricity (kWh/day)")
    ax.set_title("Outdoor temperature vs daily electricity")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "temp_vs_electricity.png", dpi=FIG_DPI)
    plt.close(fig)


def plot_gas_vs_hdd(merged: pd.DataFrame, reg: "Regression | None") -> None:
    """月次HDD vs ガス使用量の散布図と回帰線。切片がベースガス。"""
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(merged["hdd"], merged["gas_m3"], color="tab:purple")
    for _, row in merged.iterrows():
        ax.annotate(row["month"].strftime("%Y-%m"), (row["hdd"], row["gas_m3"]),
                    fontsize=7, xytext=(4, 4), textcoords="offset points")

    if reg:
        x = np.linspace(0, merged["hdd"].max(), 50)
        ax.plot(x, reg.slope * x + reg.intercept, color="tab:red",
                label=f"{reg.slope:.3f} m3/HDD + base {reg.intercept:.1f} m3 (R2={reg.r2:.2f})")
        ax.legend()

    ax.set_xlabel("Monthly heating degree days (base 18 deg C)")
    ax.set_ylabel("Gas (m3/month)")
    ax.set_title("Heating degree days vs monthly gas usage")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "gas_vs_hdd.png", dpi=FIG_DPI)
    plt.close(fig)
