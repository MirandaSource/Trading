# Resultados del backtest (datos reales, velas 1h, feed IEX)

Periodo: 2024-09-16 → 2026-09-14. Ejecutable con `python backtest.py --years 2 [--sweep]`.
Sin comisiones (Alpaca no cobra en acciones) y sin slippage: los números reales serían algo peores.

## Estrategia actual del bot (SMA 9/21, trailing stop 2%, take profit 6%)

| Símbolo | Operaciones | Win rate | Retorno compuesto | Max drawdown | Comprar y mantener |
|---------|-------------|----------|-------------------|--------------|--------------------|
| AAPL    | 92          | 40,2%    | +30,0%            | -8,4%        | +54,7%             |
| MSFT    | 92          | 40,2%    | +9,0%             | -10,7%       | +17,0%             |

Salidas: ~70% por trailing stop, ~25% por cruce bajista, ~3% por take profit. El stop del 2%
es muy estrecho para velas de 1 hora: corta la mayoría de operaciones antes de que el
take profit del 6% llegue a activarse.

## Barrido de parámetros

La mejor combinación in-sample (SMA 9/50, stop 8%, TP 12%) da +70,8% en AAPL y -5,3% en MSFT.
Ninguna combinación probada supera de forma consistente a comprar y mantener los dos valores.

Validación fuera de muestra (primer año vs segundo año):

| Configuración | AAPL año 1 | AAPL año 2 | MSFT año 1 | MSFT año 2 |
|---------------|-----------|-----------|-----------|-----------|
| 9/21 stop 2% TP 6% | +21,3% | +7,3% | -4,9% | +15,9% |
| 9/50 stop 8% TP 12% | +16,8% | +36,7% | -3,4% | -3,3% |
| Comprar y mantener | +19,3% | +30,4% | +19,0% | -1,7% |

Los resultados cambian de signo entre periodos y entre valores: el buen resultado del barrido
es sobreajuste, no una ventaja real.

## Conclusiones

1. No existe una configuración que "siempre gane". Esta estrategia gana en tendencias y pierde
   en mercados laterales; el 60% de las operaciones cierran en pérdida y la rentabilidad depende
   de unas pocas operaciones grandes.
2. En este periodo la estrategia rinde por debajo de comprar y mantener en ambos valores.
3. Si se quiere mejorar la expectativa, las palancas con más impacto según los datos son ampliar
   el stop (2% es ruido en velas de 1h) y filtrar por tendencia, no afinar las SMA.
4. Antes de pasar a dinero real: semanas de paper trading, y asumir que el drawdown real puede
   superar el 10% observado aquí.
