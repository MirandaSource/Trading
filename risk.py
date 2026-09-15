"""Dimensionamiento de posición por objetivo de beneficio, con tope de riesgo del 2%."""

import math
from dataclasses import dataclass


@dataclass
class PositionSizing:
    qty: int
    risk_amount: float
    risk_per_share: float
    notional: float
    expected_profit: float
    reason: str = ""

    def describe(self) -> str:
        return (
            f"qty={self.qty} ({self.reason}) | nocional={self.notional:.2f} "
            f"| riesgo máx={self.risk_amount:.2f} (riesgo/acción={self.risk_per_share:.2f}) "
            f"| beneficio objetivo={self.expected_profit:.2f}"
        )


def calculate_position_size(
    equity: float,
    buying_power: float,
    price: float,
    risk_per_trade: float = 0.02,
    stop_percent: float = 2.0,
    take_profit_percent: float = 6.0,
    target_profit_min: float = 100.0,
    target_profit_max: float = 1000.0,
    max_position_pct: float = 0.25,
) -> PositionSizing:
    """Calcula el número de acciones a comprar.

    Punto de partida: acciones necesarias para alcanzar `target_profit_max` si salta el
    take profit. Ese número se recorta sucesivamente por el riesgo máximo admitido
    (equity * risk_per_trade frente a la pérdida en el stop), por la exposición máxima
    (`max_position_pct` del equity) y por el poder de compra. Si el resultado ni
    siquiera alcanza `target_profit_min`, se devuelve igualmente la cantidad recortada
    (el motivo indica qué límite mandó) y quien llama decide si opera.
    """
    if price <= 0 or equity <= 0:
        return PositionSizing(0, 0.0, 0.0, 0.0, 0.0, "precio o equity inválidos")

    risk_amount = equity * risk_per_trade
    risk_per_share = price * (stop_percent / 100.0)
    profit_per_share = price * (take_profit_percent / 100.0)
    if risk_per_share <= 0 or profit_per_share <= 0:
        return PositionSizing(0, risk_amount, risk_per_share, 0.0, 0.0, "porcentajes inválidos")

    qty = math.floor(target_profit_max / profit_per_share)
    reason = f"objetivo de beneficio {target_profit_max:.0f} USD"

    limits = [
        (math.floor(risk_amount / risk_per_share), f"riesgo máximo {risk_per_trade:.0%} del equity"),
        (math.floor((equity * max_position_pct) / price), f"exposición máxima {max_position_pct:.0%}"),
        (math.floor(buying_power / price), "poder de compra disponible"),
    ]
    for limit_qty, limit_reason in limits:
        if limit_qty < qty:
            qty, reason = limit_qty, limit_reason

    qty = max(qty, 0)
    expected_profit = qty * profit_per_share
    if qty > 0 and expected_profit < target_profit_min:
        reason += f" (por debajo del objetivo mínimo de {target_profit_min:.0f} USD)"

    return PositionSizing(
        qty=qty,
        risk_amount=risk_amount,
        risk_per_share=risk_per_share,
        notional=qty * price,
        expected_profit=expected_profit,
        reason=reason,
    )
