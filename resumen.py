"""Resumen de la cuenta: equity, posiciones abiertas y operaciones cerradas.

Uso:
    python resumen.py              # últimos 7 días de operaciones
    python resumen.py --days 30
"""

import argparse
from datetime import datetime, timedelta, timezone

from alpaca.trading.enums import OrderSide, QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest, GetPortfolioHistoryRequest

from broker import AlpacaBroker
from config import Config


def _fmt_money(value: float) -> str:
    return f"{value:,.2f} USD"


def _fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def print_account(broker: AlpacaBroker) -> None:
    account = broker.get_account()
    equity = float(account.equity)
    last_equity = float(account.last_equity or equity)
    change = equity - last_equity
    pct = (change / last_equity * 100.0) if last_equity else 0.0

    print("=== CUENTA ===")
    print(f"Cuenta:        {account.account_number} ({account.status})")
    print(f"Equity:        {_fmt_money(equity)}")
    print(f"Efectivo:      {_fmt_money(float(account.cash))}")
    print(f"Poder compra:  {_fmt_money(float(account.buying_power))}")
    print(f"Hoy:           {_fmt_money(change)} ({_fmt_pct(pct)})")


def print_positions(broker: AlpacaBroker) -> None:
    positions = broker.trading.get_all_positions()
    print("\n=== POSICIONES ABIERTAS ===")
    if not positions:
        print("(ninguna)")
        return
    total = 0.0
    for p in positions:
        pl = float(p.unrealized_pl)
        total += pl
        print(
            f"{p.symbol:6} qty={p.qty:>8} entrada={float(p.avg_entry_price):>9.2f} "
            f"actual={float(p.current_price):>9.2f} "
            f"P&L={_fmt_money(pl):>16} ({_fmt_pct(float(p.unrealized_plpc) * 100)})"
        )
    print(f"P&L no realizado total: {_fmt_money(total)}")


def print_closed_trades(broker: AlpacaBroker, days: int) -> None:
    """Empareja compras y ventas ejecutadas por símbolo para estimar el P&L realizado."""
    after = datetime.now(timezone.utc) - timedelta(days=days)
    orders = broker.trading.get_orders(
        GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=after, limit=500)
    )
    filled = [o for o in orders if o.filled_qty and float(o.filled_qty) > 0]
    filled.sort(key=lambda o: o.filled_at)

    print(f"\n=== OPERACIONES EJECUTADAS (últimos {days} días) ===")
    if not filled:
        print("(ninguna)")
        return

    lots: dict[str, list[list[float]]] = {}
    realized: dict[str, float] = {}
    wins = losses = 0

    for o in filled:
        qty = float(o.filled_qty)
        price = float(o.filled_avg_price)
        symbol = o.symbol
        print(
            f"{o.filled_at:%Y-%m-%d %H:%M} {symbol:6} {o.side.value.upper():4} "
            f"qty={qty:>8.2f} precio={price:>9.2f}"
        )
        if o.side == OrderSide.BUY:
            lots.setdefault(symbol, []).append([qty, price])
            continue
        remaining = qty
        while remaining > 0 and lots.get(symbol):
            lot = lots[symbol][0]
            matched = min(remaining, lot[0])
            pl = (price - lot[1]) * matched
            realized[symbol] = realized.get(symbol, 0.0) + pl
            if pl >= 0:
                wins += 1
            else:
                losses += 1
            lot[0] -= matched
            remaining -= matched
            if lot[0] <= 0:
                lots[symbol].pop(0)

    if realized:
        print("\nP&L realizado por símbolo:")
        for symbol, pl in realized.items():
            print(f"  {symbol:6} {_fmt_money(pl)}")
        total = sum(realized.values())
        closed = wins + losses
        print(f"  TOTAL  {_fmt_money(total)}")
        if closed:
            print(f"  cierres: {closed} | ganadores: {wins} | perdedores: {losses} "
                  f"| win rate: {wins / closed * 100:.1f}%")
    else:
        print("\n(sin cierres completos todavía)")


def print_portfolio_history(broker: AlpacaBroker, days: int) -> None:
    period = f"{max(days, 1)}D"
    history = broker.trading.get_portfolio_history(
        GetPortfolioHistoryRequest(period=period, timeframe="1D")
    )
    values = [v for v in (history.equity or []) if v]
    if len(values) < 2:
        return
    change = values[-1] - values[0]
    pct = change / values[0] * 100.0 if values[0] else 0.0
    print(f"\n=== EVOLUCIÓN ({period}) ===")
    print(f"Inicio: {_fmt_money(values[0])} -> Fin: {_fmt_money(values[-1])}")
    print(f"Variación: {_fmt_money(change)} ({_fmt_pct(pct)})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Resumen de cuenta y operaciones")
    parser.add_argument("--days", type=int, default=7, help="días de histórico (por defecto 7)")
    args = parser.parse_args()

    cfg = Config.from_env()
    broker = AlpacaBroker(cfg)

    print_account(broker)
    print_positions(broker)
    print_portfolio_history(broker, args.days)
    print_closed_trades(broker, args.days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
