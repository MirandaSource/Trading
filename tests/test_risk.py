from risk import calculate_position_size


def test_riesgo_nunca_supera_el_2_por_ciento():
    equity = 100_000.0
    sizing = calculate_position_size(equity, 1_000_000.0, price=50.0)
    perdida_en_stop = sizing.qty * sizing.risk_per_share
    assert perdida_en_stop <= equity * 0.02


def test_objetivo_de_beneficio_maximo_limita_el_tamano():
    # Equity grande: manda el objetivo de 1.000 USD, no los topes de riesgo.
    sizing = calculate_position_size(10_000_000.0, 10_000_000.0, price=100.0)
    assert sizing.qty == 166  # 1000 / (100 * 6%)
    assert sizing.expected_profit <= 1000.0
    assert "objetivo de beneficio" in sizing.reason


def test_poder_de_compra_limita_el_tamano():
    sizing = calculate_position_size(1_000_000.0, 500.0, price=100.0)
    assert sizing.qty == 5
    assert sizing.reason.startswith("poder de compra disponible")


def test_exposicion_maxima_limita_el_tamano():
    sizing = calculate_position_size(
        10_000_000.0, 10_000_000.0, price=100.0, target_profit_max=1_000_000.0
    )
    assert sizing.qty == 25_000  # 25% de 10M / 100
    assert "exposición máxima" in sizing.reason


def test_cuenta_pequena_marca_objetivo_minimo_no_alcanzado():
    sizing = calculate_position_size(1_000.0, 1_000.0, price=200.0, max_position_pct=1.0)
    assert sizing.qty == 5  # riesgo 20 USD / 4 USD por acción
    assert sizing.expected_profit < 100.0
    assert "objetivo mínimo" in sizing.reason


def test_entradas_invalidas():
    assert calculate_position_size(0.0, 0.0, price=100.0).qty == 0
    assert calculate_position_size(1000.0, 1000.0, price=0.0).qty == 0
