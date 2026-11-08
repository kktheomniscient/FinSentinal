import pytest
from app.tools import financial_math_tool as fm


def test_de():
    assert fm.debt_to_equity(150, 100) == 1.5
    with pytest.raises(ValueError):
        fm.debt_to_equity(1, 0)


def test_margin_and_growth():
    assert fm.net_margin(20, 200) == 10.0
    assert fm.yoy_growth(120, 100) == 20.0
    assert fm.yoy_growth(-50, -100) == 50.0
    r = fm.yoy_net_margin_growth(20, 200, 10, 200)
    assert r["change_pp"] == 5.0 and r["relative_growth_pct"] == 100.0
