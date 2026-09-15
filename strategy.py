"""Estrategia de cruce de medias móviles (SMA 9 / SMA 21) sobre velas de 1 hora."""

from dataclasses import dataclass
from enum import Enum

import pandas as pd


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class StrategyResult:
    symbol: str
    signal: Signal
    last_price: float
    fast_sma: float
    slow_sma: float
    prev_fast_sma: float
    prev_slow_sma: float

    def describe(self) -> str:
        return (
            f"{self.symbol}: {self.signal.value} | precio={self.last_price:.2f} "
            f"| SMA rápida {self.prev_fast_sma:.2f}->{self.fast_sma:.2f} "
            f"| SMA lenta {self.prev_slow_sma:.2f}->{self.slow_sma:.2f}"
        )


def compute_signal(
    symbol: str, bars: pd.DataFrame, fast: int = 9, slow: int = 21
) -> StrategyResult | None:
    """Devuelve la señal de la última vela cerrada, o None si no hay datos suficientes.

    Cruce alcista (fast cruza por encima de slow) -> BUY.
    Cruce bajista (fast cruza por debajo de slow) -> SELL.
    """
    if bars is None or len(bars) < slow + 1:
        return None

    close = bars["close"].astype(float)
    fast_sma = close.rolling(window=fast).mean()
    slow_sma = close.rolling(window=slow).mean()

    f_now, f_prev = fast_sma.iloc[-1], fast_sma.iloc[-2]
    s_now, s_prev = slow_sma.iloc[-1], slow_sma.iloc[-2]
    if pd.isna(f_prev) or pd.isna(s_prev):
        return None

    if f_prev <= s_prev and f_now > s_now:
        signal = Signal.BUY
    elif f_prev >= s_prev and f_now < s_now:
        signal = Signal.SELL
    else:
        signal = Signal.HOLD

    return StrategyResult(
        symbol=symbol,
        signal=signal,
        last_price=float(close.iloc[-1]),
        fast_sma=float(f_now),
        slow_sma=float(s_now),
        prev_fast_sma=float(f_prev),
        prev_slow_sma=float(s_prev),
    )
