"""Rules of the book, checked without market data."""

from __future__ import annotations

import unittest

import pandas as pd

from medmom.strategy import (
    AI_DD_SLACK,
    BASE_SLEEVE,
    MAX_STRESS_LOSS,
    TARGET_GROSS,
    TOP_N,
    Row,
    max_drawdown,
    position_ratio,
    select,
    shares_for,
    sharpe_ratio,
    sleeve_weights,
)


def _row(ticker, group, stress_dd, ret_126=0.20):
    return Row(
        ticker=ticker,
        company=ticker,
        group=group,
        price=100.0,
        sma50=98.0,
        sma200=90.0,
        ret_126=ret_126,
        stress_dd=stress_dd,
        dollar_vol=30_000_000.0,
        dist_sma50=100 / 98 - 1,
        dd_20=-0.01,
        ret_contest=0.01,
    )


class SelectTests(unittest.TestCase):
    def test_least_drawdown_ranks_first(self):
        rows = [
            _row("AAA", "medical", -0.06),
            _row("BBB", "medical", -0.01),
            _row("CCC", "ai_core", -0.04),
        ]
        chosen = [r.ticker for r in select(rows, top_n=2, min_ai=0)]
        self.assertEqual(chosen, ["BBB", "CCC"])

    def test_ai_swap_within_slack(self):
        medical = [_row(f"M{i}", "medical", -0.01) for i in range(6)]
        ai = [_row(f"A{i}", "ai_applied", -0.01 - AI_DD_SLACK + 0.001) for i in range(3)]
        chosen = select(medical + ai)
        self.assertEqual(len(chosen), TOP_N)
        self.assertGreaterEqual(sum(1 for r in chosen if r.ai), 3)

    def test_ai_swap_stops_when_the_hole_is_deeper(self):
        medical = [_row(f"M{i}", "medical", -0.01) for i in range(6)]
        ai = [_row(f"A{i}", "ai_core", -0.01 - AI_DD_SLACK - 0.01) for i in range(3)]
        chosen = select(medical + ai)
        self.assertTrue(all(not r.ai for r in chosen))

    def test_risk_budget_matches_the_eligibility_cap(self):
        self.assertAlmostEqual(BASE_SLEEVE * MAX_STRESS_LOSS, 0.012)


class WeightTests(unittest.TestCase):
    def test_unused_slots_stay_out_of_the_sleeve(self):
        rows = [_row("AAA", "medical", -0.02), _row("BBB", "ai_core", -0.03)]
        returns = pd.DataFrame({"AAA": [0.01, -0.01] * 15, "BBB": [0.0, 0.01] * 15})
        weights = sleeve_weights(rows, returns)
        self.assertAlmostEqual(weights["AAA"], BASE_SLEEVE / TOP_N)
        self.assertAlmostEqual(sum(weights.values()), TARGET_GROSS)

    def test_high_correlation_cuts_the_sleeve(self):
        rows = [_row("AAA", "medical", -0.02), _row("BBB", "medical", -0.02)]
        returns = pd.DataFrame({"AAA": [0.01, -0.02, 0.015] * 10, "BBB": [0.01, -0.02, 0.015] * 10})
        weights = sleeve_weights(rows, returns)
        self.assertLess(weights["AAA"], BASE_SLEEVE / TOP_N)
        self.assertAlmostEqual(sum(weights.values()), TARGET_GROSS)

    def test_boxx_topup_clears_the_gross_target(self):
        weights = {"AAA": 0.025, "BOXX": 0.575}
        prices = {"AAA": 100.0, "BOXX": 120.0}
        holding = shares_for(weights, prices, fx_sgd_per_usd=1.30)
        self.assertGreaterEqual(position_ratio(holding, prices, 1.30), TARGET_GROSS)
        self.assertLess(position_ratio(holding, prices, 1.30), TARGET_GROSS + 0.002)

    def test_drawdown_and_sharpe_on_a_known_path(self):
        self.assertAlmostEqual(max_drawdown([100, 110, 90, 95]), 90 / 110 - 1)
        steady = pd.Series([0.01, 0.011, 0.012, 0.009])
        self.assertGreater(sharpe_ratio(steady), 0)
        self.assertEqual(sharpe_ratio(pd.Series([0.01, 0.01, 0.01])), 0.0)


if __name__ == "__main__":
    unittest.main()
