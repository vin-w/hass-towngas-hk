from custom_components.towngas_hk.sensor import calc_towngas_bill
from custom_components.towngas_hk.const import BASIC_CHARGE, MAINTENANCE_FEE, DEFAULT_FUEL_ADJUSTMENT_RATE


def test_calc_examples():
    # samples provided by user; values now reflect the corrected billing logic.
    assert calc_towngas_bill(576, 3.360) == 193.73
    assert calc_towngas_bill(624, 4.010) == 213.05


def test_zero_usage():
    # zero consumption triggers the initial charge plus maintenance fee
    expected = BASIC_CHARGE + MAINTENANCE_FEE
    assert calc_towngas_bill(0, 4.52) == round(expected, 2)


def test_large_usage():
    # simply exercise high value, result should be positive float
    val = calc_towngas_bill(300000, 5.0)
    assert isinstance(val, float)
    assert val > 0


def test_rate_parsing_edge():
    # ensure that a normal (nonzero) fuel rate is handled correctly. 100 MJ
    # produces a gas charge above the basic charge so no extra BASIC_CHARGE is
    # levied; maintenance fee and fuel adjustment are included.
    rate = DEFAULT_FUEL_ADJUSTMENT_RATE
    gas = 100 * (28.55 / 100.0)
    fuel_adj = 100 * (rate / 100.0)
    expected = round(gas + fuel_adj + MAINTENANCE_FEE, 2)
    assert calc_towngas_bill(100, rate) == expected


def test_basic_charge_added_only_for_low_gas_charge():
    # if the gas charge is below HK$20, then BASIC_CHARGE should be added; for
    # larger usage it should not. use the default fuel adjustment rate to mimic
    # real-world values.
    rate = DEFAULT_FUEL_ADJUSTMENT_RATE
    small = calc_towngas_bill(1, rate)
    gas_small = 1 * (28.55 / 100.0)
    fuel_small = 1 * (rate / 100.0)
    assert small == round(gas_small + fuel_small + MAINTENANCE_FEE + BASIC_CHARGE, 2)
    large = calc_towngas_bill(100, rate)
    gas_large = 100 * (28.55 / 100.0)
    fuel_large = 100 * (rate / 100.0)
    assert large == round(gas_large + fuel_large + MAINTENANCE_FEE, 2)

