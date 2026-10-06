import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from simulation.engine import compute_performance


def _history():
    return [
        {"date": "2025-01-01", "close": 10000},
        {"date": "2025-06-01", "close": 11000},
        {"date": "2026-01-01", "close": 12000},
    ]


def test_compute_performance_basic_gain():
    result = compute_performance(
        history=_history(),
        start_date="2025-01-01",
        end_date="2026-01-01",
        initial_amount=100000,
        dividends=None,
        include_dividends=False,
    )
    assert result["initial_price"] == 10000
    assert result["final_price"] == 12000
    assert result["shares_bought"] == pytest.approx(10.0)
    assert result["final_value"] == pytest.approx(120000.0)
    assert result["net_gain_or_loss"] == pytest.approx(20000.0)
    assert result["performance_percent"] == pytest.approx(20.0)


def test_compute_performance_includes_dividends_in_matching_years():
    dividends = [
        {"year": "2025", "amount": 100, "yield_percent": 1.0},
        {"year": "2024", "amount": 90, "yield_percent": 1.0},
    ]
    result = compute_performance(
        history=_history(),
        start_date="2025-01-01",
        end_date="2026-01-01",
        initial_amount=100000,
        dividends=dividends,
        include_dividends=True,
    )
    # shares_bought = 10 ; seul le dividende 2025 tombe dans la plage de dates couvertes
    assert result["dividends_received"] == pytest.approx(10.0 * 100)


def test_compute_performance_rejects_invalid_period():
    with pytest.raises(ValueError):
        compute_performance(
            history=_history(),
            start_date="2026-01-01",
            end_date="2025-01-01",
            initial_amount=100000,
        )


def test_compute_performance_rejects_insufficient_history():
    with pytest.raises(ValueError):
        compute_performance(
            history=[{"date": "2025-01-01", "close": 10000}],
            start_date="2025-01-01",
            end_date="2026-01-01",
            initial_amount=100000,
        )
