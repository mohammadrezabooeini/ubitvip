from typing import Any, Awaitable, Callable

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods import TelegramMethod
from aiogram.types import MessageEntity


CUSTOM_EMOJI_IDS = {
    "1️⃣": "5235776368905562305",
    "2️⃣": "5237704680372447424",
    "3️⃣": "5238044171767393675",
    "👋": "5472055112702629499",
    "⏳": "5451732530048802485",
    "❌": "5465665476971471368",
    "✅": "5427009714745517609",
    "💰": "5375296873982604963",
    "🔗": "5375129357373165375",
    "⚠️": "5447644880824181073",
    "👤": "5373012449597335010",
    "📌": "5397782960512444700",
    "🎁": "5199749070830197566",
    "☎️": "5465169893580086142",
    "🎩": "5467480195143310096",
    "⭐": "4988289890769699938",
    "📊": "5431577498364158238",
    "🔄": "5264727218734524899",
    "🔎": "5188311512791393083",
    "📣": "5469903029144657419",
    "➕": "5226945370684140473",
    "➖": "5229113891081956317",
    "📥": "5433811242135331842",
    "📈": "5373001317042101552",
    "📉": "5361748661640372834",
    "🔥": "5420315771991497307",
    "✌️": "5469986291380657759",
    "⬅️": "5469735272017043817",
}

RTL_MARK = "\u200f"


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def ensure_rtl(text: str) -> str:
    return "\n".join(
        (
            line
            if not line or line.startswith(RTL_MARK)
            else f"{RTL_MARK}{line}"
        )
        for line in text.split("\n")
    )


def build_custom_emoji_entities(text: str) -> list[MessageEntity]:
    entities: list[MessageEntity] = []
    emojis = sorted(CUSTOM_EMOJI_IDS, key=len, reverse=True)
    index = 0

    while index < len(text):
        matched = next(
            (
                emoji
                for emoji in emojis
                if text.startswith(emoji, index)
            ),
            None,
        )
        if matched is None:
            index += 1
            continue

        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=_utf16_length(text[:index]),
                length=_utf16_length(matched),
                custom_emoji_id=CUSTOM_EMOJI_IDS[matched],
            )
        )
        index += len(matched)

    return entities


def build_bold_entity(text: str, value: str) -> MessageEntity:
    index = text.rfind(value)
    if index < 0:
        raise ValueError("Bold value was not found in text.")

    return MessageEntity(
        type="bold",
        offset=_utf16_length(text[:index]),
        length=_utf16_length(value),
    )


class CustomEmojiMiddleware(BaseRequestMiddleware):
    @staticmethod
    def _apply(
        method: TelegramMethod[Any],
        text_field: str,
        entities_field: str,
        parse_mode_field: str,
    ) -> None:
        text = getattr(method, text_field, None)
        if not isinstance(text, str) or not text:
            return
        if getattr(method, entities_field, None):
            return

        text = ensure_rtl(text)
        setattr(method, text_field, text)

        entities = build_custom_emoji_entities(text)
        if entities:
            setattr(method, entities_field, entities)
            if hasattr(method, parse_mode_field):
                setattr(method, parse_mode_field, None)

    async def __call__(
        self,
        make_request: Callable[
            [Bot, TelegramMethod[Any]],
            Awaitable[Any],
        ],
        bot: Bot,
        method: TelegramMethod[Any],
    ) -> Any:
        self._apply(method, "text", "entities", "parse_mode")
        self._apply(
            method,
            "caption",
            "caption_entities",
            "parse_mode",
        )
        return await make_request(bot, method)
