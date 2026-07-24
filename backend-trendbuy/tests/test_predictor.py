from datetime import datetime

import pandas as pd

from services.predictor import classify_best_moment, history_sparkline


def make_history(rows: list[tuple[str, float]]) -> pd.DataFrame:
    # Same columns load_product_price_history() produces (the ones
    # classify_best_moment/history_sparkline actually read).
    return pd.DataFrame(
        {
            "fecha": [datetime.fromisoformat(fecha) for fecha, _ in rows],
            "precio": [precio for _, precio in rows],
        }
    )


def test_single_day_history_is_not_enough_for_historic_low():
    # Regression: a first-ever scrape writes one record per store, all on the
    # same day - its only price IS the minimum, so without the distinct-days
    # gate every fresh search result claimed "mínimo histórico".
    history = make_history(
        [
            ("2026-07-15T10:00:00", 100.0),
            ("2026-07-15T10:00:05", 105.0),
            ("2026-07-15T10:00:09", 110.0),
        ]
    )
    result = classify_best_moment(history)
    assert result["days_tracked"] == 1
    assert result["has_price_history"] is False


def test_two_distinct_days_enable_historic_low():
    history = make_history(
        [
            ("2026-07-14T10:00:00", 120.0),
            ("2026-07-15T10:00:00", 100.0),
        ]
    )
    result = classify_best_moment(history)
    assert result["days_tracked"] == 2
    assert result["has_price_history"] is True
    assert result["historic_min"] == "100.00"


def test_empty_history_has_no_history_flags():
    result = classify_best_moment(pd.DataFrame())
    assert result["status"] == "Sin datos"
    assert "has_price_history" not in result


def test_sparkline_takes_daily_minimum_across_stores():
    history = make_history(
        [
            ("2026-07-14T09:00:00", 120.0),
            ("2026-07-14T09:00:10", 115.0),
            ("2026-07-15T09:00:00", 100.0),
            ("2026-07-15T09:00:10", 130.0),
        ]
    )
    assert history_sparkline(history) == [115.0, 100.0]


def test_sparkline_limits_to_requested_points():
    rows = [(f"2026-06-{day:02d}T09:00:00", 100.0 + day) for day in range(1, 21)]
    history = make_history(rows)
    spark = history_sparkline(history, points=7)
    assert len(spark) == 7
    assert spark[-1] == 120.0


def test_sparkline_empty_history_is_empty():
    assert history_sparkline(pd.DataFrame()) == []
