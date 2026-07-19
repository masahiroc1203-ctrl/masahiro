"""HEMS生ログ（積算カウンタ）を electricity_hourly.csv（datetime, room, kwh）に変換する。

各チャンネルの積算カウンタを毎時0分の値に線形補間し、前後の差分から時間別kWhを求める。
家全体消費 = 買電(master) − 売電(export) + 太陽光発電(pv) で復元し、6ch合計との差を
「Other」（計測外回路）として出力するため、部屋別合計≒家全体になる。
※ エネファーム発電の自家消費分は計測外のため、家全体・Otherはその分過小評価になる。

使い方: python hems_to_hourly.py  （data/hems_raw.csv 蓄積後に実行）
"""

import sys

import pandas as pd

from config import (
    ELECTRICITY_HOURLY_CSV,
    HEMS_CHANNEL_ROOMS,
    HEMS_KWH_PER_COUNT,
    HEMS_OTHER_ROOM,
    HEMS_RAW_CSV,
)

MIN_SAMPLES = 2


def hourly_kwh(raw: pd.DataFrame, column: str) -> pd.Series:
    """積算カウンタ列を毎時値に補間し、差分をkWhにして返す。"""
    series = raw.set_index("timestamp")[column].dropna()
    if len(series) < MIN_SAMPLES:
        return pd.Series(dtype=float)
    start = series.index.min().ceil("h")
    end = series.index.max().floor("h")
    if start >= end:
        return pd.Series(dtype=float)
    grid = pd.date_range(start, end, freq="h")
    # 実測時刻と毎時グリッドを合わせて補間し、グリッド上の値だけ取り出す
    combined = series.reindex(series.index.union(grid)).interpolate(method="time")
    on_grid = combined.reindex(grid)
    kwh = on_grid.diff().dropna() * HEMS_KWH_PER_COUNT
    # カウンタリセット（機器再起動等）による負の差分は欠測として捨てる
    kwh = kwh[kwh >= 0]
    # 差分は区間終端の時刻に付くので、区間開始時刻をラベルにする
    kwh.index = kwh.index - pd.Timedelta(hours=1)
    return kwh


def convert() -> pd.DataFrame:
    raw = pd.read_csv(HEMS_RAW_CSV, parse_dates=["timestamp"])
    raw = raw.sort_values("timestamp").drop_duplicates("timestamp")

    frames: list[pd.DataFrame] = []
    channel_sums: pd.Series | None = None
    for ch, room in HEMS_CHANNEL_ROOMS.items():
        kwh = hourly_kwh(raw, f"ch{ch}")
        if kwh.empty:
            continue
        frames.append(pd.DataFrame({"datetime": kwh.index, "room": room, "kwh": kwh.to_numpy()}))
        channel_sums = kwh if channel_sums is None else channel_sums.add(kwh, fill_value=0)

    imported = hourly_kwh(raw, "master")
    if not imported.empty and channel_sums is not None:
        exported = hourly_kwh(raw, "export").reindex(imported.index).fillna(0)
        pv = hourly_kwh(raw, "pv").reindex(imported.index).fillna(0)
        total = imported - exported + pv  # エネファーム自家消費分は取得できず含まれない
        other = (total - channel_sums.reindex(total.index).fillna(0)).clip(lower=0)
        frames.append(pd.DataFrame({"datetime": other.index, "room": HEMS_OTHER_ROOM, "kwh": other.to_numpy()}))

    if not frames:
        return pd.DataFrame(columns=["datetime", "room", "kwh"])
    return pd.concat(frames).sort_values(["datetime", "room"]).reset_index(drop=True)


def main() -> None:
    if not HEMS_RAW_CSV.exists():
        print(f"{HEMS_RAW_CSV} がありません。先に poll_hems.py で蓄積してください。", file=sys.stderr)
        sys.exit(1)
    hourly = convert()
    if hourly.empty:
        print("毎時0分をまたぐサンプルがまだ足りません（1時間以上の蓄積が必要）")
        sys.exit(0)
    hourly.to_csv(ELECTRICITY_HOURLY_CSV, index=False)
    span = f"{hourly['datetime'].min()} 〜 {hourly['datetime'].max()}"
    print(f"{ELECTRICITY_HOURLY_CSV} に {len(hourly)} 行を出力しました（{span}）")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
