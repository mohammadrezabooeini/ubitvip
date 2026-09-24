import unittest
from unittest.mock import AsyncMock, patch

from services import checker


class FakeCheckerDatabase:
    def __init__(self, balance_warning_count):
        self.user = {
            "telegram_id": 10,
            "yubit_uid": "10101010",
            "last_check": None,
            "warning_count": balance_warning_count,
            "invite_link": None,
        }
        self.warning_calls = 0
        self.deactivated = False

    async def get_all_active_users(self):
        return [self.user]

    async def get_minimum_balance(self):
        return 50.0

    async def update_balance(self, telegram_id, balance):
        self.balance = balance

    async def add_warning(self, telegram_id):
        self.warning_calls += 1

    async def update_invite_link(self, telegram_id, invite_link):
        return None

    async def deactivate_user(self, telegram_id):
        self.deactivated = True


class FakeAPI:
    def __init__(self, balance):
        self.balance = balance

    async def get_balance(self, uid):
        return self.balance


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


class WeeklyCheckerTest(unittest.IsolatedAsyncioTestCase):
    async def test_third_warning_is_sent_without_removal(self):
        database = FakeCheckerDatabase(balance_warning_count=2)
        bot = FakeBot()
        remove = AsyncMock(return_value=True)

        with (
            patch.object(checker, "db", database),
            patch.object(checker, "yubit", FakeAPI(20)),
            patch.object(checker, "remove_user", remove),
        ):
            await checker.weekly_check(bot)

        self.assertEqual(database.warning_calls, 1)
        self.assertFalse(database.deactivated)
        remove.assert_not_awaited()
        self.assertIn("هشدار 3 از ۳", bot.messages[0][1])

    async def test_next_failed_check_removes_user(self):
        database = FakeCheckerDatabase(balance_warning_count=3)
        bot = FakeBot()
        remove = AsyncMock(return_value=True)

        with (
            patch.object(checker, "db", database),
            patch.object(checker, "yubit", FakeAPI(20)),
            patch.object(checker, "remove_user", remove),
        ):
            await checker.weekly_check(bot)

        self.assertEqual(database.warning_calls, 0)
        self.assertTrue(database.deactivated)
        remove.assert_awaited_once_with(bot, 10)
        self.assertIn("سه هشدار", bot.messages[0][1])

    async def test_safe_balance_sends_nothing_and_keeps_warnings(self):
        database = FakeCheckerDatabase(balance_warning_count=2)
        bot = FakeBot()
        remove = AsyncMock(return_value=True)

        with (
            patch.object(checker, "db", database),
            patch.object(checker, "yubit", FakeAPI(100)),
            patch.object(checker, "remove_user", remove),
        ):
            await checker.weekly_check(bot)

        self.assertEqual(database.warning_calls, 0)
        self.assertFalse(database.deactivated)
        self.assertEqual(bot.messages, [])
        remove.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
