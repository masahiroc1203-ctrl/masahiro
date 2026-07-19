"""動作確認用のサンプルデータを生成する。

実データが用意できるまでのプレースホルダ。東海地方の気候を模した
1年分（日次）の外気温・室温・電力使用量と、月次のガス使用量を作る。
実データを置き換えたらこのスクリプトは実行不要。
"""

import numpy as np
import pandas as pd

from config import (
    DATA_DIR,
    ELECTRICITY_CSV,
    ELECTRICITY_HOURLY_CSV,
    GAS_CSV,
    HDD_BASE_C,
    TEMPERATURE_CSV,
)

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

# 時間別・部屋別モデル（kWh/時）。想定の家:
# 1F: LDK（吹き抜け・冷房効率低め・床暖房補助でたまにエアコン暖房）
# 2F: 寝室（夜間冷房）・書斎（日中）・浴室/洗濯（朝夕）
DIURNAL_AMPLITUDE_C = 3.0  # 外気の日内変動
COOLING_BASE_C = 24.0
AC_HEAT_THRESHOLD_C = 8.0  # これより寒い日はLDKでエアコン補助暖房


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


def _hourly_by_room(dates: pd.DatetimeIndex, outdoor: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    """部屋別・時間別のkWhを生成する（ロング形式）。"""
    hours = np.arange(24)
    diurnal = DIURNAL_AMPLITUDE_C * np.sin((hours - 8) / 24 * 2 * np.pi)  # 14時ごろ最高

    frames: list[pd.DataFrame] = []
    for i, day in enumerate(dates):
        t_h = outdoor[i] + diurnal
        cooling = np.clip(t_h - COOLING_BASE_C, 0, None)
        heating = np.clip(HDD_BASE_C - t_h, 0, None)

        occupied_ldk = (hours >= 7) & (hours <= 23)
        # 吹き抜けで冷気が2Fへ逃げる分、LDKの冷房係数は他室より大きい
        ldk = (
            0.10 * occupied_ldk
            + 0.09 * cooling * ((hours >= 10) & (hours <= 22))
            + (0.04 * heating * (((hours >= 6) & (hours <= 9)) | (hours >= 17))
               if outdoor[i] < AC_HEAT_THRESHOLD_C else 0.0)
        )
        night = (hours >= 21) | (hours <= 6)
        bedroom = 0.03 * night + 0.05 * cooling * night
        study = 0.08 * ((hours >= 9) & (hours <= 18)) + 0.05 * cooling * ((hours >= 9) & (hours <= 18))
        bath_laundry = 0.15 * ((hours >= 18) & (hours <= 22)) + 0.05 * ((hours >= 6) & (hours <= 8))
        other = np.full(24, 0.22)  # 冷蔵庫・ネットワーク機器等の常時負荷

        for room, kwh in (
            ("LDK", ldk),
            ("Bedroom", bedroom),
            ("Study", study),
            ("Bath/Laundry", bath_laundry),
            ("Other/Base", other),
        ):
            noisy = np.clip(kwh + rng.normal(0, 0.02, 24), 0, None)
            frames.append(
                pd.DataFrame(
                    {
                        "datetime": day + pd.to_timedelta(hours, unit="h"),
                        "room": room,
                        "kwh": noisy.round(3),
                    }
                )
            )
    return pd.concat(frames, ignore_index=True)


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

    hourly = _hourly_by_room(dates, outdoor, rng)
    hourly["datetime"] = hourly["datetime"].dt.strftime("%Y-%m-%d %H:%M")
    hourly.to_csv(ELECTRICITY_HOURLY_CSV, index=False)

    print(f"サンプルデータを {DATA_DIR} に生成しました（{N_DAYS}日分・部屋別時間別を含む）")


if __name__ == "__main__":
    main()
