import unittest

from aiogram.methods import SendMessage

from bot.keyboards import admin_menu, main_menu
from services.custom_emoji import (
    CUSTOM_EMOJI_IDS,
    START_CUSTOM_EMOJI_ID,
    CustomEmojiMiddleware,
    build_bold_entity,
    build_custom_emoji_entities,
    ensure_rtl,
    start_custom_emoji_entity,
)


class CustomEmojiEntityTest(unittest.TestCase):
    def test_entities_use_utf16_offsets_and_lengths(self):
        entities = build_custom_emoji_entities("a👋b⚠️✅")

        self.assertEqual(len(entities), 3)
        self.assertEqual(
            [
                (
                    entity.offset,
                    entity.length,
                    entity.custom_emoji_id,
                )
                for entity in entities
            ],
            [
                (1, 2, CUSTOM_EMOJI_IDS["👋"]),
                (4, 2, CUSTOM_EMOJI_IDS["⚠️"]),
                (6, 1, CUSTOM_EMOJI_IDS["✅"]),
            ],
        )

    def test_uid_emoji_without_id_is_untouched(self):
        self.assertEqual(build_custom_emoji_entities("🆔 UID"), [])

    def test_number_emojis_use_requested_ids(self):
        entities = build_custom_emoji_entities("1️⃣ 2️⃣ 3️⃣")
        self.assertEqual(
            [entity.custom_emoji_id for entity in entities],
            [
                "5235776368905562305",
                "5237704680372447424",
                "5238044171767393675",
            ],
        )

    def test_invite_link_can_be_bolded(self):
        text = ensure_rtl(
            "🔗 لینک ورود VIP\nhttps://t.me/+ExampleInvite"
        )
        entity = build_bold_entity(
            text,
            "https://t.me/+ExampleInvite",
        )

        self.assertEqual(entity.type, "bold")
        self.assertGreater(entity.offset, 0)
        self.assertEqual(
            entity.length,
            len("https://t.me/+ExampleInvite"),
        )

    def test_every_nonempty_line_is_right_to_left(self):
        text = ensure_rtl("خط اول\n\nUID: 12345678")
        lines = text.split("\n")
        self.assertTrue(lines[0].startswith("\u200f"))
        self.assertEqual(lines[1], "")
        self.assertTrue(lines[2].startswith("\u200f"))

    def test_start_emoji_uses_requested_id(self):
        entity = start_custom_emoji_entity()
        self.assertEqual(entity.offset, 0)
        self.assertEqual(entity.length, 1)
        self.assertEqual(entity.custom_emoji_id, START_CUSTOM_EMOJI_ID)


class CustomEmojiMiddlewareTest(unittest.IsolatedAsyncioTestCase):
    async def test_outgoing_message_receives_custom_entities(self):
        method = SendMessage(chat_id=1, text="✅ انجام شد")
        middleware = CustomEmojiMiddleware()

        async def make_request(bot, outgoing_method):
            return outgoing_method

        result = await middleware(make_request, None, method)
        self.assertEqual(len(result.entities), 1)
        self.assertEqual(
            result.entities[0].custom_emoji_id,
            CUSTOM_EMOJI_IDS["✅"],
        )

    async def test_existing_entities_are_preserved(self):
        start_entity = start_custom_emoji_entity()
        method = SendMessage(
            chat_id=1,
            text="⭐",
            entities=[start_entity],
        )
        middleware = CustomEmojiMiddleware()

        async def make_request(bot, outgoing_method):
            return outgoing_method

        result = await middleware(make_request, None, method)
        self.assertEqual(result.entities, [start_entity])

    async def test_plain_message_is_made_right_to_left(self):
        method = SendMessage(chat_id=1, text="پیام بدون ایموجی")
        middleware = CustomEmojiMiddleware()

        async def make_request(bot, outgoing_method):
            return outgoing_method

        result = await middleware(make_request, None, method)
        self.assertTrue(result.text.startswith("\u200f"))


class CustomEmojiKeyboardTest(unittest.TestCase):
    def test_user_keyboard_uses_custom_icons(self):
        keyboard = main_menu()
        buttons = [
            button
            for row in keyboard.inline_keyboard
            for button in row
        ]

        self.assertEqual(len(buttons), 5)
        self.assertEqual(
            [len(row) for row in keyboard.inline_keyboard],
            [1, 1, 2, 1],
        )
        self.assertEqual(buttons[0].text, "عضویت رایگان")
        self.assertEqual(buttons[0].style, "success")
        self.assertEqual(buttons[1].style, "success")
        self.assertIsNone(buttons[2].style)
        self.assertIsNone(buttons[3].style)
        self.assertEqual(buttons[4].style, "success")
        self.assertIsNotNone(buttons[4].url)
        self.assertIsNone(buttons[4].callback_data)
        self.assertTrue(
            all(button.icon_custom_emoji_id for button in buttons)
        )
        self.assertTrue(
            all(
                emoji not in button.text
                for button in buttons
                for emoji in CUSTOM_EMOJI_IDS
            )
        )

        trial_buttons = [
            button
            for row in main_menu(trial_enabled=True).inline_keyboard
            for button in row
        ]
        self.assertEqual(len(trial_buttons), 6)
        self.assertEqual(
            trial_buttons[2].callback_data,
            "trial_vip",
        )

    def test_admin_keyboard_uses_custom_icons(self):
        buttons = [
            button
            for row in admin_menu().inline_keyboard
            for button in row
        ]

        self.assertEqual(len(buttons), 14)
        self.assertTrue(
            all(button.icon_custom_emoji_id for button in buttons)
        )


if __name__ == "__main__":
    unittest.main()
