"""Verifica la conexión con Alpaca (PAPER TRADING) e imprime el balance."""

import logging
import sys

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient

from config import Config, ConfigError
from logging_setup import setup_logging

log = logging.getLogger("check_connection")


def main() -> int:
    try:
        cfg = Config.from_env()
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    setup_logging(cfg.log_file)

    if not cfg.paper:
        log.error("ALPACA_PAPER=false: este bot solo opera contra paper trading.")
        return 2

    client = TradingClient(cfg.api_key, cfg.secret_key, paper=True)

    try:
        account = client.get_account()
    except APIError as exc:
        log.error("Fallo de autenticación/conexión con Alpaca: %s", exc)
        return 1

    log.info("Conexión OK con Alpaca Paper Trading (https://paper-api.alpaca.markets)")
    log.info("Cuenta:              %s", account.account_number)
    log.info("Estado:              %s", account.status)
    log.info("Moneda:              %s", account.currency)
    log.info("Equity:              %s", account.equity)
    log.info("Cash:                %s", account.cash)
    log.info("Buying power:        %s", account.buying_power)
    log.info("Trading bloqueado:   %s", account.trading_blocked)
    log.info("Patrón day trader:   %s", account.pattern_day_trader)

    positions = client.get_all_positions()
    if positions:
        for p in positions:
            log.info(
                "Posición abierta: %s qty=%s avg=%s P/L=%s",
                p.symbol,
                p.qty,
                p.avg_entry_price,
                p.unrealized_pl,
            )
    else:
        log.info("Sin posiciones abiertas.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
