"""Smoke test del ciclo con un broker simulado (sin red)."""

from types import SimpleNamespace

import numpy as np
import pandas as pd

import main
from config import Config


def _cfg(**kwargs) -> Config:
    return Config(api_key="k", secret_key="s", symbols=["AAPL"], **kwargs)


class FakeBroker:
    def __init__(self, prices, position=0.0):
        self.cfg = _cfg()
        self.prices = prices
        self.position = position
        self.entries: list[tuple[str, int]] = []
        self.protections: list[tuple[str, int, float]] = []
        self.closed: list[str] = []

    def reconcile_protective_orders(self, symbol):
        pass

    def get_hourly_bars(self, symbol, lookback_days=30):
        return pd.DataFrame({"close": self.prices})

    def get_position_qty(self, symbol):
        return self.position

    def get_account(self):
        return SimpleNamespace(equity="100000", buying_power="200000", account_number="X", cash="1", status="ACTIVE")

    def submit_entry(self, symbol, qty, reference_price=None):
        self.entries.append((symbol, qty))
        return SimpleNamespace(id="order-1")

    def wait_for_fill(self, order_id, timeout_seconds=60, poll=2.0):
        qty = self.entries[-1][1]
        return SimpleNamespace(filled_avg_price=str(self.prices[-1]), filled_qty=str(qty))

    def submit_protective_orders(self, symbol, qty, entry_price):
        self.protections.append((symbol, qty, entry_price))

    def close_position(self, symbol):
        self.closed.append(symbol)


def _crossover_up():
    prices = list(np.linspace(100, 90, 30)) + list(np.linspace(90, 115, 20))
    for i in range(31, len(prices) + 1):
        from strategy import Signal, compute_signal

        if compute_signal("AAPL", pd.DataFrame({"close": prices[:i]})).signal is Signal.BUY:
            return prices[:i]
    raise AssertionError("no se generó cruce alcista")


def _crossover_down():
    prices = list(np.linspace(90, 115, 30)) + list(np.linspace(115, 85, 20))
    for i in range(31, len(prices) + 1):
        from strategy import Signal, compute_signal

        if compute_signal("AAPL", pd.DataFrame({"close": prices[:i]})).signal is Signal.SELL:
            return prices[:i]
    raise AssertionError("no se generó cruce bajista")


def test_cruce_alcista_compra_y_protege():
    broker = FakeBroker(_crossover_up())
    main.process_symbol(broker, broker.cfg, "AAPL")
    assert len(broker.entries) == 1
    assert broker.entries[0][1] > 0
    assert len(broker.protections) == 1
    assert not broker.closed


def test_modo_bracket_no_envia_protecciones_extra():
    broker = FakeBroker(_crossover_up())
    cfg = _cfg(protection_mode="bracket")
    main.process_symbol(broker, cfg, "AAPL")
    assert len(broker.entries) == 1
    assert broker.protections == []


def test_cruce_alcista_con_posicion_abierta_no_duplica():
    broker = FakeBroker(_crossover_up(), position=10)
    main.process_symbol(broker, broker.cfg, "AAPL")
    assert broker.entries == []


def test_cruce_bajista_cierra_posicion():
    broker = FakeBroker(_crossover_down(), position=10)
    main.process_symbol(broker, broker.cfg, "AAPL")
    assert broker.closed == ["AAPL"]


def test_datos_insuficientes_no_opera():
    broker = FakeBroker(list(np.linspace(100, 110, 5)))
    main.process_symbol(broker, broker.cfg, "AAPL")
    assert broker.entries == [] and broker.closed == []
