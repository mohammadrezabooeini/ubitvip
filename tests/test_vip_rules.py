import unittest
from datetime import datetime, timedelta

from services.vip_rules import (
    is_insufficient_balance,
    is_warning_balance,
    needs_recheck,
    should_remove_after_warnings,
)


class VipRulesTest(unittest.TestCase):
    def test_join_and_kick_use_the_same_threshold(self) -> None:
        self.assertFalse(is_insufficient_balance(50, 50))
        self.assertTrue(is_insufficient_balance(49.99, 50))
        self.assertFalse(is_insufficient_balance(50.01, 50))

    def test_warning_zone(self) -> None:
        self.assertTrue(is_warning_balance(50, 50, 65))
        self.assertTrue(is_warning_balance(65, 50, 65))
        self.assertFalse(is_warning_balance(49.9, 50, 65))
        self.assertFalse(is_warning_balance(65.1, 50, 65))

    def test_removal_happens_after_three_warnings(self) -> None:
        self.assertFalse(should_remove_after_warnings(0))
        self.assertFalse(should_remove_after_warnings(2))
        self.assertTrue(should_remove_after_warnings(3))

    def test_needs_recheck_when_never_checked(self) -> None:
        self.assertTrue(needs_recheck(None, 7))
        self.assertTrue(needs_recheck("", 7))

    def test_needs_recheck_respects_interval(self) -> None:
        now = datetime(2026, 8, 18, 12, 0, 0)
        recent = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        old = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertFalse(needs_recheck(recent, 7, now=now))
        self.assertTrue(needs_recheck(old, 7, now=now))

    def test_invalid_last_check_is_treated_as_due(self) -> None:
        self.assertTrue(needs_recheck("not-a-date", 7))


if __name__ == "__main__":
    unittest.main()
