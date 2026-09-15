# Bot de trading SMA 9/21 sobre Alpaca (Paper Trading)

Estructura:

- `config.py` — configuración desde variables de entorno (`.env` vía python-dotenv).
- `logging_setup.py` — logging a consola y a `trading_bot.log` (rotativo).
- `strategy.py` — cruce de SMA 9 / SMA 21 sobre velas de 1 hora.
- `risk.py` — sizing por objetivo de beneficio con tope de riesgo del 2% del equity.
- `broker.py` — acceso a Alpaca (datos, cuenta, órdenes).
- `main.py` — bucle en vivo cada 15 minutos y modo `--dry-run`.
- `check_connection.py` — prueba mínima de conexión: balance y posiciones.
- `tests/` — tests unitarios de estrategia y gestión de riesgo (`pytest`).

## Uso

```bash
pip install -r requirements.txt
cp .env.example .env    # rellena ALPACA_API_KEY y ALPACA_SECRET_KEY
python main.py --dry-run   # pre-vuelo: conexión, balance, velas, SMA y sizing, sin órdenes
python main.py             # bot en vivo (ciclo cada 15 min)
pytest -q                  # tests
```

## Lógica

1. Cada 15 minutos, si el mercado está abierto, descarga velas de 1h de AAPL y MSFT.
2. Cruce alcista SMA9 > SMA21 → compra; cruce bajista → cierra la posición larga.
3. Sizing: parte de las acciones necesarias para ganar `TARGET_PROFIT_MAX` (1.000 USD)
   con el take profit del 6%, y recorta por (a) riesgo máximo del 2% del equity frente
   al stop del 2%, (b) exposición máxima `MAX_POSITION_PCT` y (c) poder de compra.
   Si el resultado queda por debajo de `TARGET_PROFIT_MIN` (100 USD) se registra en el log.
4. Protección de cada entrada según `PROTECTION_MODE`:
   - `trailing` (por defecto): market + trailing stop 2% + take profit limit 6%; el bot
     cancela la pata superviviente cuando ya no hay posición (OCO gestionado en cada ciclo).
   - `bracket`: orden bracket nativa de Alpaca con stop loss **fijo** al 2% y take profit 6%.

## Notas

- Endpoint de paper trading: `https://paper-api.alpaca.markets` (`https://alpaca.markets`
  es el sitio web, no la API). `TradingClient(..., paper=True)` lo usa automáticamente;
  el bot aborta si `ALPACA_PAPER=false`.
- Alpaca no admite trailing stop dentro de una bracket order: por eso existen los dos
  modos anteriores. El trailing real requiere el modo `trailing`.
- Solo opera en largo: el cruce bajista cierra la posición, no abre cortos.
- Datos: feed `iex` por defecto (gratuito). Usa `sip` solo si tu plan lo incluye.
