"""Bot de trading automático: cruce SMA 9/21 en velas de 1h sobre Alpaca Paper Trading.

  python main.py             # bucle en vivo, un ciclo cada 15 minutos
  python main.py --dry-run   # pre-vuelo: conexión, balance, datos e indicadores, sin órdenes
"""

import argparse
import logging
import signal
import sys
import time

from alpaca.common.exceptions import APIError

from broker import AlpacaBroker
from config import Config, ConfigError
from logging_setup import setup_logging
from risk import calculate_position_size
from strategy import Signal, compute_signal

log = logging.getLogger("bot")

_running = True


def _handle_sigterm(signum, _frame) -> None:
    global _running
    _running = False
    log.info("Señal %s recibida: parando tras el ciclo actual.", signum)


def process_symbol(broker: AlpacaBroker, cfg: Config, symbol: str) -> None:
    broker.reconcile_protective_orders(symbol)

    bars = broker.get_hourly_bars(symbol)
    result = compute_signal(symbol, bars, cfg.fast_sma, cfg.slow_sma)
    if result is None:
        log.warning("%s: datos insuficientes para calcular las SMA", symbol)
        return

    log.info(result.describe())
    position_qty = broker.get_position_qty(symbol)

    if result.signal is Signal.BUY:
        if position_qty > 0:
            log.info("%s: cruce alcista pero ya hay posición abierta (%s)", symbol, position_qty)
            return

        account = broker.get_account()
        sizing = size_for(cfg, account, result.last_price)
        log.info("%s: ALERTA cruce alcista | %s", symbol, sizing.describe())
        if sizing.qty < 1:
            log.warning("%s: tamaño de posición < 1 acción, se omite la entrada", symbol)
            return

        entry = broker.submit_entry(symbol, sizing.qty, reference_price=result.last_price)
        filled = broker.wait_for_fill(entry.id)
        if filled is None:
            log.error("%s: la entrada no se llenó; revisa el estado de la orden", symbol)
            return

        entry_price = float(filled.filled_avg_price or result.last_price)
        filled_qty = int(float(filled.filled_qty))
        log.info("%s: COMPRA ejecutada qty=%s precio medio=%.2f", symbol, filled_qty, entry_price)
        if cfg.protection_mode != "bracket":
            broker.submit_protective_orders(symbol, filled_qty, entry_price)

    elif result.signal is Signal.SELL:
        if position_qty > 0:
            log.info("%s: ALERTA cruce bajista, cerrando posición de %s acciones", symbol, position_qty)
            broker.close_position(symbol)
        else:
            log.info("%s: cruce bajista sin posición abierta (no se opera en corto)", symbol)

    else:
        log.info("%s: sin cruce, manteniendo (posición=%s)", symbol, position_qty)


def size_for(cfg: Config, account, price: float):
    return calculate_position_size(
        equity=float(account.equity),
        buying_power=float(account.buying_power),
        price=price,
        risk_per_trade=cfg.risk_per_trade,
        stop_percent=cfg.trailing_stop_percent,
        take_profit_percent=cfg.take_profit_percent,
        target_profit_min=cfg.target_profit_min,
        target_profit_max=cfg.target_profit_max,
        max_position_pct=cfg.max_position_pct,
    )


def preflight(broker: AlpacaBroker, cfg: Config) -> int:
    """Validación sin enviar órdenes: cuenta, balance, datos e indicadores."""
    account = broker.get_account()
    log.info("DRY-RUN | cuenta=%s estado=%s", account.account_number, account.status)
    log.info("DRY-RUN | equity=%s cash=%s buying_power=%s", account.equity, account.cash, account.buying_power)
    log.info("DRY-RUN | mercado abierto: %s", broker.is_market_open())

    problems = 0
    for symbol in cfg.symbols:
        try:
            bars = broker.get_hourly_bars(symbol)
            result = compute_signal(symbol, bars, cfg.fast_sma, cfg.slow_sma)
            if result is None:
                log.warning("DRY-RUN | %s: datos insuficientes (%s velas)", symbol, len(bars))
                problems += 1
                continue
            log.info("DRY-RUN | %s velas descargadas | %s", len(bars), result.describe())
            log.info("DRY-RUN | %s: %s", symbol, size_for(cfg, account, result.last_price).describe())
            log.info("DRY-RUN | %s: posición actual=%s", symbol, broker.get_position_qty(symbol))
        except APIError as exc:
            log.error("DRY-RUN | error de la API de Alpaca con %s: %s", symbol, exc)
            problems += 1

    log.info("DRY-RUN | finalizado sin enviar órdenes (%s incidencias)", problems)
    return 1 if problems else 0


def run_cycle(broker: AlpacaBroker, cfg: Config) -> None:
    if not broker.is_market_open():
        log.info("Mercado cerrado: se omite el ciclo de revisión.")
        return

    for symbol in cfg.symbols:
        try:
            process_symbol(broker, cfg, symbol)
        except APIError as exc:
            log.error("Error de la API de Alpaca procesando %s: %s", symbol, exc)
        except Exception:
            log.exception("Error inesperado procesando %s", symbol)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot SMA 9/21 sobre Alpaca Paper Trading")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="verifica conexión, balance, datos e indicadores sin enviar órdenes",
    )
    args = parser.parse_args()

    try:
        cfg = Config.from_env()
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    setup_logging(cfg.log_file)
    if not cfg.paper:
        log.error("ALPACA_PAPER=false: este bot solo opera contra paper trading.")
        return 2

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    broker = AlpacaBroker(cfg)
    if args.dry_run:
        try:
            return preflight(broker, cfg)
        except APIError as exc:
            log.error("Fallo de conexión con Alpaca: %s", exc)
            return 1

    account = broker.get_account()
    log.info(
        "Bot iniciado | cuenta=%s equity=%s símbolos=%s SMA=%s/%s intervalo=%ss",
        account.account_number,
        account.equity,
        ",".join(cfg.symbols),
        cfg.fast_sma,
        cfg.slow_sma,
        cfg.poll_interval_seconds,
    )
    log.info("Modo de protección: %s", cfg.protection_mode)

    while _running:
        started = time.time()
        log.info("--- Inicio de ciclo de revisión ---")
        try:
            run_cycle(broker, cfg)
        except APIError as exc:
            log.error("Error de conexión con la API de Alpaca: %s", exc)
        except Exception:
            log.exception("Error inesperado en el ciclo")
        log.info("--- Fin de ciclo (%.1fs) ---", time.time() - started)

        slept = 0.0
        while _running and slept < cfg.poll_interval_seconds:
            time.sleep(min(5.0, cfg.poll_interval_seconds - slept))
            slept += 5.0

    log.info("Bot detenido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
