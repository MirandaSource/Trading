"""Capa de acceso a Alpaca: datos históricos, cuenta y envío de órdenes."""

import logging
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.common.exceptions import APIError
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import (
    OrderClass,
    OrderSide,
    OrderStatus,
    QueryOrderStatus,
    TimeInForce,
)
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
    TrailingStopOrderRequest,
)

from config import Config

log = logging.getLogger("broker")


class AlpacaBroker:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        # paper=True apunta a https://paper-api.alpaca.markets
        self.trading = TradingClient(cfg.api_key, cfg.secret_key, paper=cfg.paper)
        self.data = StockHistoricalDataClient(cfg.api_key, cfg.secret_key)
        self.feed = DataFeed(os.getenv("ALPACA_DATA_FEED", "iex").lower())

    # --- cuenta / mercado -------------------------------------------------
    def get_account(self):
        return self.trading.get_account()

    def is_market_open(self) -> bool:
        return bool(self.trading.get_clock().is_open)

    def get_position_qty(self, symbol: str) -> float:
        try:
            return float(self.trading.get_open_position(symbol).qty)
        except APIError:
            return 0.0

    # --- datos ------------------------------------------------------------
    def get_hourly_bars(self, symbol: str, lookback_days: int = 30) -> pd.DataFrame:
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Hour,
            start=datetime.now(timezone.utc) - timedelta(days=lookback_days),
            feed=self.feed,
        )
        bars = self.data.get_stock_bars(request).df
        if bars.empty:
            return bars
        if isinstance(bars.index, pd.MultiIndex):
            bars = bars.xs(symbol, level="symbol")
        return bars.sort_index()

    # --- órdenes ----------------------------------------------------------
    def submit_entry(self, symbol: str, qty: int, reference_price: float | None = None):
        """Envía la compra.

        PROTECTION_MODE=bracket: bracket nativa de Alpaca (stop loss fijo + take profit).
        PROTECTION_MODE=trailing (por defecto): market simple; las patas de protección
        se envían tras el fill con `submit_protective_orders`, porque Alpaca no admite
        trailing stop dentro de una bracket.
        """
        if self.cfg.protection_mode == "bracket":
            if reference_price is None:
                raise ValueError("reference_price es obligatorio en modo bracket")
            stop_price = round(reference_price * (1 - self.cfg.trailing_stop_percent / 100.0), 2)
            tp_price = round(reference_price * (1 + self.cfg.take_profit_percent / 100.0), 2)
            request = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=tp_price),
                stop_loss=StopLossRequest(stop_price=stop_price),
            )
            log.info(
                "Bracket %s | stop %.2f (-%.2f%%) | take profit %.2f (+%.2f%%)",
                symbol,
                stop_price,
                self.cfg.trailing_stop_percent,
                tp_price,
                self.cfg.take_profit_percent,
            )
        else:
            request = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )

        order = self.trading.submit_order(request)
        log.info("Orden de COMPRA enviada: %s qty=%s id=%s", symbol, qty, order.id)
        return order

    def submit_protective_orders(self, symbol: str, qty: int, entry_price: float) -> None:
        """Trailing stop del X% + take profit fijo del Y% (OCO gestionado por el bot)."""
        trail = self.trading.submit_order(
            TrailingStopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                trail_percent=self.cfg.trailing_stop_percent,
            )
        )
        log.info(
            "Trailing stop %.2f%% enviado para %s qty=%s id=%s",
            self.cfg.trailing_stop_percent,
            symbol,
            qty,
            trail.id,
        )

        take_profit_price = round(entry_price * (1 + self.cfg.take_profit_percent / 100.0), 2)
        tp = self.trading.submit_order(
            LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                limit_price=take_profit_price,
            )
        )
        log.info(
            "Take profit %.2f%% (limit %.2f) enviado para %s id=%s",
            self.cfg.take_profit_percent,
            take_profit_price,
            symbol,
            tp.id,
        )

    def wait_for_fill(self, order_id, timeout_seconds: int = 60, poll: float = 2.0):
        """Espera el fill de una orden; devuelve la orden o None si no llenó a tiempo."""
        import time

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            order = self.trading.get_order_by_id(order_id)
            if order.status == OrderStatus.FILLED:
                return order
            if order.status in (
                OrderStatus.CANCELED,
                OrderStatus.EXPIRED,
                OrderStatus.REJECTED,
            ):
                log.error("Orden %s terminó en estado %s", order_id, order.status)
                return None
            time.sleep(poll)
        log.warning("Orden %s sin fill tras %ss", order_id, timeout_seconds)
        return None

    def open_sell_orders(self, symbol: str) -> list:
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
        return [o for o in self.trading.get_orders(request) if o.side == OrderSide.SELL]

    def cancel_open_sell_orders(self, symbol: str) -> None:
        for order in self.open_sell_orders(symbol):
            try:
                self.trading.cancel_order_by_id(order.id)
                log.info("Orden de venta cancelada: %s id=%s", symbol, order.id)
            except APIError as exc:
                log.error("No se pudo cancelar la orden %s: %s", order.id, exc)

    def close_position(self, symbol: str):
        self.cancel_open_sell_orders(symbol)
        order = self.trading.close_position(symbol)
        log.info("Cierre de posición enviado: %s id=%s", symbol, order.id)
        return order

    def reconcile_protective_orders(self, symbol: str) -> None:
        """Si ya no hay posición, cancela las órdenes de venta huérfanas (OCO manual)."""
        if self.get_position_qty(symbol) == 0 and self.open_sell_orders(symbol):
            log.info("Sin posición en %s: cancelando órdenes de protección restantes", symbol)
            self.cancel_open_sell_orders(symbol)
