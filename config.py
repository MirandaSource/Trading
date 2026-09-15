"""Configuración central del bot. Todo se lee de variables de entorno."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    pass


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None or raw.strip() == "" else float(raw)


@dataclass
class Config:
    api_key: str
    secret_key: str
    paper: bool = True
    symbols: list[str] = field(default_factory=lambda: ["AAPL", "MSFT"])

    fast_sma: int = 9
    slow_sma: int = 21

    risk_per_trade: float = 0.02
    trailing_stop_percent: float = 2.0
    take_profit_percent: float = 6.0
    max_position_pct: float = 0.25

    # Objetivo de beneficio por operación usado para dimensionar la posición.
    target_profit_min: float = 100.0
    target_profit_max: float = 1000.0

    # "trailing": market + trailing stop 2% + take profit limit 6% (OCO gestionado).
    # "bracket": orden bracket nativa de Alpaca (stop loss fijo 2% + take profit 6%).
    protection_mode: str = "trailing"

    poll_interval_seconds: int = 15 * 60
    log_file: str = "trading_bot.log"

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv(override=False)

        api_key = os.getenv("ALPACA_API_KEY", "").strip()
        secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()
        if not api_key or not secret_key:
            raise ConfigError(
                "Faltan ALPACA_API_KEY y/o ALPACA_SECRET_KEY en el entorno. "
                "Exportalas antes de ejecutar el bot."
            )

        symbols = [
            s.strip().upper()
            for s in os.getenv("ALPACA_SYMBOLS", "AAPL,MSFT").split(",")
            if s.strip()
        ]

        return cls(
            api_key=api_key,
            secret_key=secret_key,
            paper=os.getenv("ALPACA_PAPER", "true").lower() != "false",
            symbols=symbols,
            fast_sma=int(_env_float("FAST_SMA", 9)),
            slow_sma=int(_env_float("SLOW_SMA", 21)),
            risk_per_trade=_env_float("RISK_PER_TRADE", 0.02),
            trailing_stop_percent=_env_float("TRAILING_STOP_PERCENT", 2.0),
            take_profit_percent=_env_float("TAKE_PROFIT_PERCENT", 6.0),
            max_position_pct=_env_float("MAX_POSITION_PCT", 0.25),
            target_profit_min=_env_float("TARGET_PROFIT_MIN", 100.0),
            target_profit_max=_env_float("TARGET_PROFIT_MAX", 1000.0),
            protection_mode=os.getenv("PROTECTION_MODE", "trailing").lower(),
            poll_interval_seconds=int(_env_float("POLL_INTERVAL_SECONDS", 15 * 60)),
            log_file=os.getenv("LOG_FILE", "trading_bot.log"),
        )
