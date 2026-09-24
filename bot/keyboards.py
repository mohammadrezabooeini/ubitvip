from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import REGISTER_LINK
from services.custom_emoji import CUSTOM_EMOJI_IDS


def _button(
    text: str,
    emoji: str,
    callback_data: str | None = None,
    url: str | None = None,
    style: str | None = None,
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
        url=url,
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS[emoji],
        style=style,
    )


def main_menu() -> InlineKeyboardMarkup:
    """ساخت منوی اصلی ربات."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(
                    text="عضویت",
                    emoji="⭐",
                    callback_data="join_vip",
                    style="success",
                )
            ],
            [
                _button(
                    text="وضعیت حساب",
                    emoji="👤",
                    callback_data="status",
                    style="success",
                )
            ],
            [
                _button(
                    text="کمپین",
                    emoji="🎁",
                    callback_data="campaign",
                ),
                _button(
                    text="پشتیبانی",
                    emoji="☎️",
                    callback_data="support",
                ),
            ],
            [
                _button(
                    text="ثبت‌نام در صرافی",
                    emoji="🎩",
                    url=REGISTER_LINK,
                    style="success",
                )
            ],
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(
                    text="آمار ربات",
                    emoji="📊",
                    callback_data="admin:stats",
                ),
                _button(
                    text="چک لحظه‌ای VIPها",
                    emoji="🔄",
                    callback_data="admin:refresh",
                ),
            ],
            [
                _button(
                    text="جستجوی کاربر",
                    emoji="🔎",
                    callback_data="admin:search",
                ),
                _button(
                    text="پیام همگانی",
                    emoji="📣",
                    callback_data="admin:broadcast",
                ),
            ],
            [
                _button(
                    text="افزودن VIP",
                    emoji="➕",
                    callback_data="admin:add",
                ),
                _button(
                    text="حذف VIP",
                    emoji="➖",
                    callback_data="admin:remove",
                ),
            ],
            [
                _button(
                    text="تنظیم کمپین",
                    emoji="🎁",
                    callback_data="admin:campaign",
                ),
                _button(
                    text="لینک یکبار مصرف",
                    emoji="🔗",
                    callback_data="admin:invite",
                ),
            ],
            [
                _button(
                    text="خروجی Excel",
                    emoji="📥",
                    callback_data="admin:export",
                ),
                _button(
                    text="گزارش کامل حجم و کمیسیون",
                    emoji="📈",
                    callback_data="admin:report",
                ),
            ],
            [
                _button(
                    text="منوی کاربری",
                    emoji="👤",
                    callback_data="admin:user_menu",
                )
            ],
        ]
    )


def admin_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(
                    text="بازگشت به پنل ادمین",
                    emoji="⬅️",
                    callback_data="admin:back",
                )
            ]
        ]
    )


def broadcast_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(
                    text="ارسال",
                    emoji="✅",
                    callback_data="admin:broadcast:confirm",
                ),
                _button(
                    text="لغو",
                    emoji="❌",
                    callback_data="admin:broadcast:cancel",
                ),
            ]
        ]
    )


def remove_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(
                    text="اخراج و غیرفعال‌سازی",
                    emoji="✅",
                    callback_data="admin:remove:confirm",
                ),
                _button(
                    text="لغو",
                    emoji="❌",
                    callback_data="admin:remove:cancel",
                ),
            ]
        ]
    )