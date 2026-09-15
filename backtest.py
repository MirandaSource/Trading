"""Backtest de la estrategia de cruce de medias sobre velas de 1 hora.

Simula la misma lógica del bot: entrada larga en el cruce alcista, salida por
trailing stop, take profit o cruce bajista. Todo con datos reales de Alpaca.

  python backtest.py                      # AAPL y MSFT, 2 años, parámetros por defecto
  python backtest.py --sweep              # barrido de parámetros
  python backtest.py --symbols AAPL --years 3
"""

import argparse
import itertools
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from config import Config


@dataclass
class Trade:
    symbol: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    reason: str

    @property
    def pct(self) -> float:
        return (self.exit_price / self.entry_price - 1) * 100.0


def load_bars(cfg: Config, symbol: str, years: float) -> pd.DataFrame:
    client = StockHistoricalDataClient(cfg.api_key, cfg.secret_key)
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Hour,
        start=datetime.now(timezone.utc) - timedelta(days=int(365 * years)),
        feed=DataFeed.IEX,
    )
    bars = client.get_stock_bars(request).df
    if isinstance(bars.index, pd.MultiIndex):
        bars = bars.xs(symbol, level="symbol")
    return bars.sort_index()


def backtest(
    symbol: str,
    bars: pd.DataFrame,
    fast: int = 9,
    slow: int = 21,
    stop_percent: float = 2.0,
    take_profit_percent: float = 6.0,
    commission_pct: float = 0.0,
    trend_filter: int | None = None,
) -> list[Trade]:
    """Devuelve la lista de operaciones simuladas.

    Entrada al cierre de la vela del cruce alcista. Dentro de cada vela posterior se
    evalúa primero el stop (peor caso) y después el take profit. `trend_filter` exige
    que el precio esté por encima de la SMA de ese periodo para permitir entradas.
    """
    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    fast_sma = close.rolling(fast).mean()
    slow_sma = close.rolling(slow).mean()
    trend_sma = close.rolling(trend_filter).mean() if trend_filter else None

    trades: list[Trade] = []
    in_pos = False
    entry_price = peak = 0.0
    entry_time = None

    for i in range(1, len(bars)):
        f_now, f_prev = fast_sma.iloc[i], fast_sma.iloc[i - 1]
        s_now, s_prev = slow_sma.iloc[i], slow_sma.iloc[i - 1]
        if pd.isna(f_prev) or pd.isna(s_prev):
            continue

        if in_pos:
            peak = max(peak, high.iloc[i])
            stop_price = peak * (1 - stop_percent / 100.0)
            tp_price = entry_price * (1 + take_profit_percent / 100.0)

            if low.iloc[i] <= stop_price:
                trades.append(Trade(symbol, entry_time, entry_price, bars.index[i], stop_price, "trailing stop"))
                in_pos = False
                continue
            if high.iloc[i] >= tp_price:
                trades.append(Trade(symbol, entry_time, entry_price, bars.index[i], tp_price, "take profit"))
                in_pos = False
                continue
            if f_prev >= s_prev and f_now < s_now:
                trades.append(Trade(symbol, entry_time, entry_price, bars.index[i], close.iloc[i], "cruce bajista"))
                in_pos = False
                continue
        else:
            if f_prev <= s_prev and f_now > s_now:
                if trend_sma is not None and (
                    pd.isna(trend_sma.iloc[i]) or close.iloc[i] < trend_sma.iloc[i]
                ):
                    continue
                in_pos = True
                entry_price = close.iloc[i] * (1 + commission_pct / 100.0)
                peak = high.iloc[i]
                entry_time = bars.index[i]

    return trades


def summarize(trades: list[Trade]) -> dict:
    if not trades:
        return {"operaciones": 0}
    pcts = pd.Series([t.pct for t in trades])
    wins = pcts[pcts > 0]
    losses = pcts[pcts <= 0]
    equity = (1 + pcts / 100).cumprod()
    drawdown = (equity / equity.cummax() - 1).min() * 100
    return {
        "operaciones": len(trades),
        "win_rate_%": round(len(wins) / len(pcts) * 100, 1),
        "media_%": round(pcts.mean(), 2),
        "mediana_%": round(pcts.median(), 2),
        "ganancia_media_%": round(wins.mean(), 2) if len(wins) else 0.0,
        "perdida_media_%": round(losses.mean(), 2) if len(losses) else 0.0,
        "retorno_compuesto_%": round((equity.iloc[-1] - 1) * 100, 2),
        "max_drawdown_%": round(drawdown, 2),
    }


def buy_and_hold_pct(bars: pd.DataFrame) -> float:
    close = bars["close"].astype(float)
    return round((close.iloc[-1] / close.iloc[0] - 1) * 100, 2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest de la estrategia SMA")
    parser.add_argument("--symbols", default="AAPL,MSFT")
    parser.add_argument("--years", type=float, default=2.0)
    parser.add_argument("--sweep", action="store_true", help="barrido de parámetros")
    parser.add_argument("--commission-pct", type=float, default=0.0)
    args = parser.parse_args()

    cfg = Config.from_env()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    data = {s: load_bars(cfg, s, args.years) for s in symbols}

    for symbol, bars in data.items():
        print(f"\n== {symbol}: {len(bars)} velas de 1h, {bars.index[0].date()} -> {bars.index[-1].date()}")
        print(f"   comprar y mantener: {buy_and_hold_pct(bars)} %")
        trades = backtest(symbol, bars, commission_pct=args.commission_pct)
        print(f"   SMA 9/21 + stop 2% + TP 6%: {summarize(trades)}")
        motivos = pd.Series([t.reason for t in trades]).value_counts().to_dict() if trades else {}
        print(f"   salidas por motivo: {motivos}")

    if args.sweep:
        print("\n== Barrido de parámetros (retorno compuesto %, por símbolo)")
        combos = itertools.product([5, 9, 12, 20], [21, 50, 100], [2.0, 4.0, 8.0], [6.0, 12.0, 100.0], [None, 200])
        rows = []
        for fast, slow, stop, tp, trend in combos:
            if fast >= slow:
                continue
            row = {"fast": fast, "slow": slow, "stop%": stop, "tp%": tp, "filtro_tendencia": trend}
            total = 0.0
            for symbol, bars in data.items():
                res = summarize(
                    backtest(symbol, bars, fast, slow, stop, tp, args.commission_pct, trend)
                )
                row[symbol] = res.get("retorno_compuesto_%", 0.0)
                row[f"{symbol}_ops"] = res.get("operaciones", 0)
                total += row[symbol]
            row["total"] = round(total, 2)
            rows.append(row)
        table = pd.DataFrame(rows).sort_values("total", ascending=False)
        print(table.head(15).to_string(index=False))
        print("\n   peores combinaciones:")
        print(table.tail(5).to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
