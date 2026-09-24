from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, List

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.admin_auth import AdminFilter
from bot.keyboards import (
    admin_back_keyboard,
    admin_menu,
    broadcast_confirmation_keyboard,
    main_menu,
    remove_confirmation_keyboard,
)
from config import logger
from constants import messages as msg
from database.database import db
from services.channel import (
    create_invite_link,
    remove_user,
    revoke_invite_link,
)
from services.admin import broadcast_copy, refresh_all_vip_balances
from services.excel_export import build_vip_excel
from services.yubit_api import validate_uid, yubit
from services.trading_report import (
    format_decimal,
    get_standard_reports,
)
from services.vip_rules import is_insufficient_balance

admin_router = Router(name="admin")
admin_router.message.filter(AdminFilter())
admin_router.callback_query.filter(AdminFilter())


class AdminStates(StatesGroup):
    waiting_search = State()
    waiting_broadcast = State()
    confirm_broadcast = State()
    waiting_add = State()
    waiting_remove = State()
    confirm_remove = State()
    waiting_campaign = State()
    waiting_minimum = State()


class SupportReplyFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool | dict[str, int]:
        if message.reply_to_message is None:
            return False
        user_id = await db.get_support_user(
            admin_chat_id=message.chat.id,
            admin_message_id=message.reply_to_message.message_id,
        )
        if user_id is None:
            return False
        return {"support_user_id": user_id}


@admin_router.message(Command("admin"))
async def open_admin_panel(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()
    await message.answer(
        msg.ADMIN_WELCOME,
        reply_markup=admin_menu(),
    )


@admin_router.message(SupportReplyFilter())
async def admin_support_reply(
    message: Message,
    support_user_id: int,
    state: FSMContext,
) -> None:
    try:
        await state.clear()
        await message.bot.send_message(
            support_user_id,
            msg.SUPPORT_REPLY_HEADER,
        )
        await message.bot.copy_message(
            chat_id=support_user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await message.answer("✅ پاسخ برای کاربر ارسال شد.")
    except Exception:
        logger.exception(
            "Admin support reply failed for user_id=%s",
            support_user_id,
        )
        await message.answer(msg.SUPPORT_DELIVERY_FAILED)


def _value(row: Any, key: str, default: Any = "-") -> Any:
    value = row[key]
    return default if value is None or value == "" else value


async def _send_line_chunks(
    message: Message,
    heading: str,
    lines: Iterable[str],
) -> None:
    chunks: List[str] = []
    current = heading

    for line in lines:
        candidate = f"{current}\n{line}"
        if len(candidate) > 3800:
            chunks.append(current)
            current = line
        else:
            current = candidate

    chunks.append(current)
    for chunk in chunks:
        await message.answer(chunk)


@admin_router.callback_query(F.data == "admin:back")
async def admin_back(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.answer(
        msg.ADMIN_WELCOME,
        reply_markup=admin_menu(),
    )
    await call.answer()


@admin_router.callback_query(F.data == "admin:user_menu")
async def show_user_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    trial_state = await db.get_trial_state()
    await call.message.answer(
        msg.WELCOME.format(first_name=call.from_user.first_name),
        reply_markup=main_menu(
            trial_enabled=trial_state["enabled"]
        ),
    )
    await call.answer()


@admin_router.callback_query(F.data == "admin:stats")
async def admin_stats(call: CallbackQuery) -> None:
    try:
        stats = await db.get_admin_stats()
        await call.message.answer(
            msg.ADMIN_STATS.format(
                total_bot_users=stats["total_bot_users"],
                total_vip_records=stats["total_vip_records"],
                active_vips=stats["active_vips"] or 0,
                inactive_vips=stats["inactive_vips"] or 0,
                active_balance_total=round(
                    float(stats["active_balance_total"] or 0),
                    4,
                ),
                total_warnings=stats["total_warnings"] or 0,
                latest_check=stats["latest_check"] or "هنوز انجام نشده",
            ),
            reply_markup=admin_back_keyboard(),
        )
    except Exception:
        logger.exception("Admin stats error")
        await call.message.answer(msg.ERROR_GENERIC)
    finally:
        await call.answer()


@admin_router.callback_query(F.data == "admin:refresh")
async def admin_refresh(call: CallbackQuery) -> None:
    await call.answer()
    progress = await call.message.answer(msg.ADMIN_REFRESH_STARTED)

    try:
        minimum_balance = await db.get_minimum_balance()
        result = await refresh_all_vip_balances(minimum_balance)
        await progress.edit_text(
            msg.ADMIN_REFRESH_SUMMARY.format(
                checked=result.checked,
                failed=result.failed,
                below_minimum=result.below_minimum,
            )
        )

        lines = []
        for user in result.users:
            if not user["ok"]:
                lines.append(
                    f"❌ UID {user['uid']} | دریافت موجودی ناموفق"
                )
                continue

            marker = "⚠️" if user["below_minimum"] else "✅"
            name = user["first_name"] or "-"
            lines.append(
                f"{marker} {name} | UID {user['uid']} | "
                f"{user['balance']} USDT"
            )

        if lines:
            await _send_line_chunks(
                call.message,
                "موجودی لحظه‌ای VIPهای فعال:",
                lines,
            )
        await call.message.answer(
            msg.ADMIN_WELCOME,
            reply_markup=admin_menu(),
        )
    except Exception:
        logger.exception("Admin live refresh error")
        await progress.edit_text(msg.ERROR_GENERIC)


@admin_router.callback_query(F.data == "admin:search")
async def admin_search_start(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(AdminStates.waiting_search)
    await call.message.answer(
        msg.ADMIN_SEARCH_PROMPT,
        reply_markup=admin_back_keyboard(),
    )
    await call.answer()


@admin_router.message(AdminStates.waiting_search)
async def admin_search_result(
    message: Message,
    state: FSMContext,
) -> None:
    identifier = (message.text or "").strip()
    if not identifier.isdigit():
        await message.answer(msg.ADMIN_SEARCH_PROMPT)
        return

    try:
        user = await db.find_user(identifier)
        if user is None:
            await message.answer(
                msg.ADMIN_USER_NOT_FOUND,
                reply_markup=admin_back_keyboard(),
            )
            await state.clear()
            return

        live_balance = await yubit.get_balance(user["yubit_uid"])
        if live_balance is not None:
            await db.update_balance(
                user["telegram_id"],
                live_balance,
                record_check=False,
            )

        await message.answer(
            msg.ADMIN_USER_INFO.format(
                telegram_id=user["telegram_id"],
                username=(
                    f"@{user['username']}" if user["username"] else "-"
                ),
                first_name=_value(user, "first_name"),
                uid=user["yubit_uid"],
                status=user["vip_status"],
                stored_balance=user["balance"],
                live_balance=(
                    live_balance
                    if live_balance is not None
                    else "خطا در دریافت"
                ),
                last_check=_value(user, "last_check"),
                warning_count=user["warning_count"],
            ),
            reply_markup=admin_back_keyboard(),
        )
    except Exception:
        logger.exception("Admin user search error")
        await message.answer(msg.ERROR_GENERIC)
    finally:
        await state.clear()


@admin_router.callback_query(F.data == "admin:add")
async def admin_add_start(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(AdminStates.waiting_add)
    await call.message.answer(
        msg.ADMIN_ADD_PROMPT,
        reply_markup=admin_back_keyboard(),
    )
    await call.answer()


@admin_router.message(AdminStates.waiting_add)
async def admin_add_user(
    message: Message,
    state: FSMContext,
) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer(msg.ADMIN_ADD_PROMPT)
        return

    telegram_id_raw, uid = parts
    if (
        not telegram_id_raw.isdigit()
        or int(telegram_id_raw) <= 0
        or not validate_uid(uid)
    ):
        await message.answer(msg.ADMIN_ADD_PROMPT)
        return

    telegram_id = int(telegram_id_raw)
    invite_link = None

    try:
        bot_user = await db.get_bot_user(telegram_id)
        existing = await db.get_user(telegram_id)
        profile = bot_user or existing
        if profile is None:
            await message.answer(
                msg.ADMIN_ADD_USER_UNKNOWN,
                reply_markup=admin_back_keyboard(),
            )
            return

        if (
            existing is not None
            and existing["vip_status"] == "active"
        ):
            await message.answer(msg.ALREADY_VIP)
            return
        if existing is not None and existing["invite_link"]:
            revoked = await revoke_invite_link(
                message.bot,
                existing["invite_link"],
            )
            if not revoked:
                await message.answer(msg.ADMIN_REMOVE_FAILED)
                return

        validation = await yubit.validate_user(uid)
        if not validation["success"]:
            await message.answer(msg.VALIDATION_FAILED)
            return

        balance = float(validation["balance"])
        minimum_balance = await db.get_minimum_balance()
        if is_insufficient_balance(balance, minimum_balance):
            await message.answer(
                msg.INSUFFICIENT_BALANCE.format(
                    min_balance=minimum_balance,
                    balance=balance,
                )
            )
            return

        invite_link = await create_invite_link(message.bot)
        status = await db.register_user(
            telegram_id=telegram_id,
            username=profile["username"],
            first_name=profile["first_name"],
            yubit_uid=uid,
            balance=balance,
            invite_link=invite_link,
        )

        if status == "already_active":
            await revoke_invite_link(message.bot, invite_link)
            await message.answer(msg.ALREADY_VIP)
            return
        if status == "uid_taken":
            await revoke_invite_link(message.bot, invite_link)
            await message.answer(msg.UID_IN_USE)
            return

        delivery = "موفق"
        try:
            await message.bot.send_message(
                telegram_id,
                msg.ADMIN_VIP_INVITATION.format(
                    uid=uid,
                    balance=balance,
                    invite_link=invite_link,
                ),
            )
        except Exception:
            logger.warning(
                "Admin-created VIP invite delivery failed.",
                exc_info=True,
            )
            delivery = "ناموفق؛ کاربر می‌تواند از منوی عضویت لینک جدید بگیرد"

        await message.answer(
            msg.ADMIN_ADD_SUCCESS.format(
                telegram_id=telegram_id,
                uid=uid,
                balance=balance,
                delivery=delivery,
            ),
            reply_markup=admin_back_keyboard(),
        )
    except Exception:
        logger.exception("Admin add VIP error")
        if invite_link:
            await revoke_invite_link(message.bot, invite_link)
        await message.answer(msg.ERROR_GENERIC)
    finally:
        await state.clear()


@admin_router.callback_query(F.data == "admin:remove")
async def admin_remove_start(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(AdminStates.waiting_remove)
    await call.message.answer(
        msg.ADMIN_REMOVE_PROMPT,
        reply_markup=admin_back_keyboard(),
    )
    await call.answer()


@admin_router.message(AdminStates.waiting_remove)
async def admin_remove_preview(
    message: Message,
    state: FSMContext,
) -> None:
    identifier = (message.text or "").strip()
    if not identifier.isdigit():
        await message.answer(msg.ADMIN_REMOVE_PROMPT)
        return

    user = await db.find_user(identifier)
    if user is None:
        await message.answer(
            msg.ADMIN_USER_NOT_FOUND,
            reply_markup=admin_back_keyboard(),
        )
        await state.clear()
        return

    await state.update_data(
        remove_telegram_id=user["telegram_id"],
    )
    await state.set_state(AdminStates.confirm_remove)
    await message.answer(
        msg.ADMIN_REMOVE_CONFIRM.format(
            telegram_id=user["telegram_id"],
            username=(
                f"@{user['username']}" if user["username"] else "-"
            ),
            uid=user["yubit_uid"],
            status=user["vip_status"],
            balance=user["balance"],
        ),
        reply_markup=remove_confirmation_keyboard(),
    )


@admin_router.callback_query(F.data == "admin:remove:confirm")
async def admin_remove_confirm(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    telegram_id = data.get("remove_telegram_id")
    if telegram_id is None:
        await call.message.answer(msg.ERROR_GENERIC)
        await call.answer()
        await state.clear()
        return

    try:
        user = await db.get_user(int(telegram_id))
        if user is None:
            await call.message.answer(msg.ADMIN_USER_NOT_FOUND)
            return

        invite_link = user["invite_link"]
        if invite_link:
            revoked = await revoke_invite_link(
                call.bot,
                invite_link,
            )
            if not revoked:
                await call.message.answer(msg.ADMIN_REMOVE_FAILED)
                return

        removed = await remove_user(call.bot, int(telegram_id))
        if not removed:
            await call.message.answer(msg.ADMIN_REMOVE_FAILED)
            return

        await db.update_invite_link(int(telegram_id), None)
        await db.deactivate_user(int(telegram_id))

        try:
            await call.bot.send_message(
                int(telegram_id),
                msg.ADMIN_REMOVED_USER_NOTICE,
            )
        except Exception:
            logger.warning(
                "Could not notify manually removed VIP user.",
                exc_info=True,
            )

        await call.message.answer(
            msg.ADMIN_REMOVE_SUCCESS,
            reply_markup=admin_menu(),
        )
    except Exception:
        logger.exception("Admin remove VIP error")
        await call.message.answer(msg.ERROR_GENERIC)
    finally:
        await call.answer()
        await state.clear()


@admin_router.callback_query(F.data == "admin:remove:cancel")
async def admin_remove_cancel(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    await call.message.answer(
        msg.ADMIN_CANCELLED,
        reply_markup=admin_menu(),
    )
    await call.answer()


@admin_router.callback_query(F.data == "admin:export")
async def admin_export_excel(call: CallbackQuery) -> None:
    await call.answer()
    try:
        users = await db.get_all_vip_users()
        if not users:
            await call.message.answer(msg.ADMIN_EXPORT_EMPTY)
            return

        document = BufferedInputFile(
            build_vip_excel(users),
            filename=(
                f"vip-users-{datetime.now().strftime('%Y-%m-%d-%H%M')}.xlsx"
            ),
        )
        await call.message.answer_document(
            document,
            caption=msg.ADMIN_EXPORT_CAPTION.format(
                count=len(users),
            ),
        )
    except Exception:
        logger.exception("Admin Excel export error")
        await call.message.answer(msg.ERROR_GENERIC)


@admin_router.callback_query(F.data == "admin:campaign")
async def admin_campaign_start(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(AdminStates.waiting_campaign)
    await call.message.answer(
        msg.ADMIN_CAMPAIGN_PROMPT,
        reply_markup=admin_back_keyboard(),
    )
    await call.answer()


@admin_router.message(AdminStates.waiting_campaign)
async def admin_campaign_save(
    message: Message,
    state: FSMContext,
) -> None:
    try:
        await db.set_campaign(
            source_chat_id=message.chat.id,
            source_message_id=message.message_id,
        )
        await message.answer(
            msg.ADMIN_CAMPAIGN_SAVED,
            reply_markup=admin_menu(),
        )
    except Exception:
        logger.exception("Admin campaign save error")
        await message.answer(msg.ERROR_GENERIC)
    finally:
        await state.clear()


@admin_router.callback_query(F.data == "admin:invite")
async def admin_create_invite(call: CallbackQuery) -> None:
    try:
        invite_link = await create_invite_link(call.bot)
        await call.message.answer(
            msg.ADMIN_INVITE_CREATED.format(
                invite_link=invite_link,
            ),
            reply_markup=admin_back_keyboard(),
        )
    except Exception:
        logger.exception("Admin one-time invite creation error")
        await call.message.answer(msg.ERROR_GENERIC)
    finally:
        await call.answer()


@admin_router.callback_query(F.data == "admin:trial")
async def admin_toggle_trial(call: CallbackQuery) -> None:
    try:
        state = await db.toggle_trial()
        status = "فعال ✅" if state["enabled"] else "غیرفعال ❌"
        await call.message.answer(
            msg.ADMIN_TRIAL_STATUS.format(status=status),
            reply_markup=admin_back_keyboard(),
        )
    except Exception:
        logger.exception("Admin trial toggle error")
        await call.message.answer(msg.ERROR_GENERIC)
    finally:
        await call.answer()


@admin_router.callback_query(F.data == "admin:minimum")
async def admin_minimum_start(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    try:
        current = await db.get_minimum_balance()
        await state.set_state(AdminStates.waiting_minimum)
        await call.message.answer(
            msg.ADMIN_MINIMUM_PROMPT.format(
                current=format_decimal(Decimal(str(current)))
            ),
            reply_markup=admin_back_keyboard(),
        )
    except Exception:
        logger.exception("Admin minimum setting start error")
        await call.message.answer(msg.ERROR_GENERIC)
    finally:
        await call.answer()


@admin_router.message(AdminStates.waiting_minimum)
async def admin_minimum_save(
    message: Message,
    state: FSMContext,
) -> None:
    try:
        value = Decimal((message.text or "").strip())
        if not value.is_finite() or value < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await message.answer(msg.ADMIN_MINIMUM_INVALID)
        return

    try:
        await db.set_minimum_balance(float(value))
        await message.answer(
            msg.ADMIN_MINIMUM_SAVED.format(
                value=format_decimal(value)
            ),
            reply_markup=admin_menu(),
        )
        await state.clear()
    except Exception:
        logger.exception("Admin minimum setting save error")
        await message.answer(msg.ERROR_GENERIC)


@admin_router.callback_query(F.data == "admin:report")
async def admin_full_report(call: CallbackQuery) -> None:
    await call.answer()
    progress = await call.message.answer(msg.ADMIN_REPORT_LOADING)
    try:
        reports = await get_standard_reports()

        def values(prefix: str) -> dict[str, str]:
            report = reports[prefix]
            return {
                f"{prefix}_spot": format_decimal(
                    report.spot_total_usdt
                ),
                f"{prefix}_futures": format_decimal(
                    report.futures_total_usdt
                ),
                f"{prefix}_total": format_decimal(
                    report.effective_volume_usdt
                ),
                f"{prefix}_commission": format_decimal(
                    report.commission_usdt
                ),
            }

        report_values = {
            **values("today"),
            **values("week"),
            **values("month"),
        }
        await progress.edit_text(
            msg.ADMIN_REPORT.format(**report_values),
            reply_markup=admin_back_keyboard(),
        )
    except Exception:
        logger.exception("Admin full trading report error")
        await progress.edit_text(msg.ERROR_GENERIC)


@admin_router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(AdminStates.waiting_broadcast)
    await call.message.answer(
        msg.ADMIN_BROADCAST_PROMPT,
        reply_markup=admin_back_keyboard(),
    )
    await call.answer()


@admin_router.message(AdminStates.waiting_broadcast)
async def admin_broadcast_preview(
    message: Message,
    state: FSMContext,
) -> None:
    await state.update_data(
        broadcast_chat_id=message.chat.id,
        broadcast_message_id=message.message_id,
    )
    await message.bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )
    await message.answer(
        msg.ADMIN_BROADCAST_PREVIEW,
        reply_markup=broadcast_confirmation_keyboard(),
    )
    await state.set_state(AdminStates.confirm_broadcast)


@admin_router.callback_query(F.data == "admin:broadcast:confirm")
async def admin_broadcast_confirm(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    from_chat_id = data.get("broadcast_chat_id")
    message_id = data.get("broadcast_message_id")

    if from_chat_id is None or message_id is None:
        await state.clear()
        await call.message.answer(msg.ERROR_GENERIC)
        await call.answer()
        return

    await call.answer()
    progress = await call.message.answer(msg.ADMIN_BROADCAST_STARTED)

    try:
        recipients = await db.get_broadcast_user_ids()
        result = await broadcast_copy(
            call.bot,
            recipients,
            int(from_chat_id),
            int(message_id),
        )
        await progress.edit_text(
            msg.ADMIN_BROADCAST_RESULT.format(
                total=result.total,
                sent=result.sent,
                failed=result.failed,
            )
        )
    except Exception:
        logger.exception("Admin broadcast error")
        await progress.edit_text(msg.ERROR_GENERIC)
    finally:
        await state.clear()
        await call.message.answer(
            msg.ADMIN_WELCOME,
            reply_markup=admin_menu(),
        )


@admin_router.callback_query(F.data == "admin:broadcast:cancel")
async def admin_broadcast_cancel(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    await call.message.answer(
        msg.ADMIN_CANCELLED,
        reply_markup=admin_menu(),
    )
    await call.answer()
