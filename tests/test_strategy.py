import numpy as np
import pandas as pd

from strategy import Signal, compute_signal


def _bars(prices) -> pd.DataFrame:
    return pd.DataFrame({"close": list(prices)})


def test_datos_insuficientes_devuelve_none():
    assert compute_signal("AAPL", _bars(np.linspace(100, 110, 10))) is None


def test_cruce_alcista_genera_buy():
    prices = list(np.linspace(100, 90, 30)) + list(np.linspace(90, 115, 20))
    signals = [compute_signal("AAPL", _bars(prices[:i])).signal for i in range(25, len(prices) + 1)]
    assert Signal.BUY in signals
    assert Signal.SELL not in signals


def test_cruce_bajista_genera_sell():
    prices = list(np.linspace(90, 115, 30)) + list(np.linspace(115, 85, 20))
    signals = [compute_signal("AAPL", _bars(prices[:i])).signal for i in range(30, len(prices) + 1)]
    assert Signal.SELL in signals


def test_tendencia_estable_mantiene_hold():
    prices = np.linspace(100, 130, 60)
    assert compute_signal("MSFT", _bars(prices)).signal is Signal.HOLD


def test_resultado_expone_precio_y_medias():
    prices = np.linspace(100, 130, 60)
    result = compute_signal("MSFT", _bars(prices))
    assert result.symbol == "MSFT"
    assert result.last_price == prices[-1]
    assert result.fast_sma > result.slow_sma
