"""単回帰のユーティリティ。analyze / room_analysis の双方から使う。"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import MIN_REGRESSION_SAMPLES


@dataclass
class Regression:
    """単回帰の結果。slope=温度感応度、intercept=ベース使用量。"""

    slope: float
    intercept: float
    r2: float
    n: int


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
