"""Score and weight rules for the 25% sleeve."""

import unittest

from medmom.composite import (
    COMBINED_CAP,
    HOLD_BUDGET,
    NAME_HOLD_CAP,
    NAME_TRADE_CAP,
    TRADE_BUDGET,
    allocate_hold,
    allocate_trades,
    hold_score,
    trade_score,
)


class ScoreTests(unittest.TestCase):
    def test_a_seven_percent_dip_outranks_a_shallow_one(self):
        deep = hold_score(0.20, -0.07, 0)
        shallow = hold_score(0.20, -0.04, 0)
        self.assertGreater(deep, shallow)

    def test_a_name_at_the_high_is_not_the_best_dip(self):
        dipped = hold_score(0.30, -0.07, 0)
        pinned = hold_score(0.30, -0.01, 0)
        self.assertGreater(dipped, pinned)

    def test_sharper_down_day_gets_the_bounce_score(self):
        self.assertGreater(trade_score(0.20, -0.03, 0), trade_score(0.20, -0.005, 0))


class WeightTests(unittest.TestCase):
    def test_hold_uses_the_ten_percent_budget_until_the_name_cap(self):
        weights = allocate_hold([("AAA", 0.9), ("BBB", 0.3), ("CCC", 0.3), ("DDD", 0.3)])
        self.assertLessEqual(max(weights.values()), NAME_HOLD_CAP)
        self.assertLessEqual(sum(weights.values()), HOLD_BUDGET + 1e-9)
        self.assertEqual(len(weights), 4)

    def test_one_signal_does_not_take_the_whole_trade_book(self):
        weights = allocate_trades([("AAA", 1.0)], hold={}, open_weights={})
        self.assertAlmostEqual(weights["AAA"], NAME_TRADE_CAP)
        self.assertLess(weights["AAA"], TRADE_BUDGET)

    def test_trade_leaves_room_for_the_hold_in_the_same_name(self):
        weights = allocate_trades([("AAA", 1.0), ("BBB", 1.0)], hold={"AAA": 0.04}, open_weights={})
        self.assertLessEqual(weights["AAA"] + 0.04, COMBINED_CAP + 1e-9)

    def test_an_open_trade_blocks_a_second_entry(self):
        weights = allocate_trades([("AAA", 1.0)], hold={}, open_weights={"AAA": 0.04})
        self.assertNotIn("AAA", weights)


if __name__ == "__main__":
    unittest.main()
