"""動作確認用のサンプルデータを生成する。

実データが用意できるまでのプレースホルダ。東海地方の気候を模した
1年分（日次）の外気温・室温・電力使用量と、月次のガス使用量を作る。
実データを置き換えたらこのスクリプトは実行不要。
"""

import numpy as np
import pandas as pd

from config import DATA_DIR, ELECTRICITY_CSV, GAS_CSV, HDD_BASE_C, TEMPERATURE_CSV

RANDOM_SEED = 42
N_DAYS = 366
END_DATE = "2026-07-18"

# 東海地方の気温モデル（年平均16°C・振幅11.5°C、1月末が最寒）
OUTDOOR_MEAN_C = 16.0
OUTDOOR_AMPLITUDE_C = 11.5
COLDEST_DAY_OF_YEAR = 28
OUTDOOR_NOISE_SD = 2.0

# 室内は冷暖房で緩和される想定
INDOOR_WINTER_TARGET_C = 20.0
INDOOR_SUMMER_TARGET_C = 27.0
INDOOR_MODERATION = 0.35  # 外気変動が室内に伝わる割合（断熱の効き）

# 電力モデル（kWh/日）
ELEC_BASE_KWH = 8.0
ELEC_HEATING_KWH_PER_DEG = 0.55  # エアコン暖房
ELEC_COOLING_KWH_PER_DEG = 0.70  # エアコン冷房
ELEC_COOLING_BASE_C = 24.0
ELEC_NOISE_SD = 1.2

# ガスモデル（m3/日）: 給湯・調理のベース + 冬の給湯温度低下・床暖房分
GAS_BASE_M3 = 0.35
GAS_HEATING_M3_PER_DEG = 0.09
GAS_NOISE_SD = 0.08


def _outdoor_temperature(dates: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """季節正弦波 + ノイズで外気温を作る。"""
    day_of_year = dates.dayofyear.to_numpy()
    phase = 2 * np.pi * (day_of_year - COLDEST_DAY_OF_YEAR) / 365.25
    seasonal = OUTDOOR_MEAN_C - OUTDOOR_AMPLITUDE_C * np.cos(phase)
    return seasonal + rng.normal(0, OUTDOOR_NOISE_SD, len(dates))


def _indoor_temperature(outdoor: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """冷暖房で目標温度に寄せた室温。中間期は外気に近づく。"""
    indoor = np.where(
        outdoor < HDD_BASE_C,
        INDOOR_WINTER_TARGET_C + INDOOR_MODERATION * (outdoor - HDD_BASE_C),
        np.where(
            outdoor > ELEC_COOLING_BASE_C,
            INDOOR_SUMMER_TARGET_C + INDOOR_MODERATION * (outdoor - ELEC_COOLING_BASE_C) * 0.3,
            outdoor * 0.6 + 9.0,  # 中間期: 空調なしで外気に追従
        ),
    )
    return indoor + rng.normal(0, 0.5, len(outdoor))


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    dates = pd.date_range(end=END_DATE, periods=N_DAYS, freq="D")

    outdoor = _outdoor_temperature(dates, rng)
    indoor = _indoor_temperature(outdoor, rng)

    heating_deg = np.clip(HDD_BASE_C - outdoor, 0, None)
    cooling_deg = np.clip(outdoor - ELEC_COOLING_BASE_C, 0, None)

    elec_kwh = (
        ELEC_BASE_KWH
        + ELEC_HEATING_KWH_PER_DEG * heating_deg
        + ELEC_COOLING_KWH_PER_DEG * cooling_deg
        + rng.normal(0, ELEC_NOISE_SD, N_DAYS)
    ).clip(min=1.0)

    gas_m3_daily = (
        GAS_BASE_M3
        + GAS_HEATING_M3_PER_DEG * heating_deg
        + rng.normal(0, GAS_NOISE_SD, N_DAYS)
    ).clip(min=0.05)

    DATA_DIR.mkdir(exist_ok=True)

    pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "indoor_temp_c": indoor.round(1),
            "outdoor_temp_c": outdoor.round(1),
        }
    ).to_csv(TEMPERATURE_CSV, index=False)

    pd.DataFrame(
        {"date": dates.strftime("%Y-%m-%d"), "electricity_kwh": elec_kwh.round(2)}
    ).to_csv(ELECTRICITY_CSV, index=False)

    # ガスは検針が月次なので月単位で出力
    gas_monthly = (
        pd.Series(gas_m3_daily, index=dates)
        .resample("MS")
        .sum()
        .round(1)
        .rename("gas_m3")
        .reset_index()
        .rename(columns={"index": "month"})
    )
    gas_monthly["month"] = gas_monthly["month"].dt.strftime("%Y-%m")
    gas_monthly.to_csv(GAS_CSV, index=False)

    print(f"サンプルデータを {DATA_DIR} に生成しました（{N_DAYS}日分）")


if __name__ == "__main__":
    main()
