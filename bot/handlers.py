import asyncio
from typing import Dict

from aiogram import F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

from bot.admin_auth import is_admin
from bot.keyboards import admin_menu, main_menu
from config import (
    ADMIN_IDS,
    REGISTER_LINK,
    UID_MAX_LENGTH,
    UID_MIN_LENGTH,
    WARNING_RANGE,
    logger,
)
from constants import messages as msg
from database.database import db
from services.channel import (
    create_invite_link,
    is_member,
    revoke_invite_link,
)
from services.custom_emoji import (
    START_CUSTOM_EMOJI_FALLBACK,
    build_bold_entity,
    build_custom_emoji_entities,
    ensure_rtl,
    start_custom_emoji_entity,
)
from services.yubit_api import validate_uid, yubit
from services.vip_rules import is_insufficient_balance, is_warning_balance

router = Router()
_user_locks: Dict[int, asyncio.Lock] = {}


class JoinVIP(StatesGroup):
    waiting_uid = State()


class Support(StatesGroup):
    waiting_message = State()


def _lock_for(telegram_id: int) -> asyncio.Lock:
    lock = _user_locks.get(telegram_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[telegram_id] = lock
    return lock


def _first_name(message: Message) -> str:
    if message.from_user and message.from_user.first_name:
        return message.from_user.first_name
    return "کاربر"


async def _send_success(
    message: Message,
    uid: str,
    balance: float,
    invite_link: str,
    minimum_balance: float,
) -> None:
    warning_text = ""
    warning_limit = minimum_balance + WARNING_RANGE
    if is_warning_balance(balance, minimum_balance, warning_limit):
        warning_text = msg.WARNING_TEXT.format(
            min_balance=minimum_balance
        )

    text = ensure_rtl(
        msg.REGISTRATION_SUCCESS.format(
            uid=uid,
            balance=balance,
            warning_text=warning_text,
            invite_link=invite_link,
        )
    )
    entities = build_custom_emoji_entities(text)
    entities.append(build_bold_entity(text, invite_link))

    await message.answer(
        text,
        entities=entities,
    )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    try:
        await message.answer(
            START_CUSTOM_EMOJI_FALLBACK,
            entities=[start_custom_emoji_entity()],
        )
        admin = is_admin(
            message.from_user.id if message.from_user else None
        )
        trial_state = await db.get_trial_state()
        await message.answer(
            (
                msg.ADMIN_WELCOME
                if admin
                else msg.WELCOME.format(first_name=_first_name(message))
            ),
            reply_markup=(
                admin_menu()
                if admin
                else main_menu(trial_enabled=trial_state["enabled"])
            ),
        )
    except Exception:
        logger.exception("Start handler error")
        await message.answer(msg.ERROR_GENERIC)


@router.message(Command("myid"))
async def show_my_telegram_id(message: Message) -> None:
    if message.from_user is None:
        return
    await message.answer(
        msg.MY_TELEGRAM_ID.format(
            telegram_id=message.from_user.id,
        )
    )


@router.chat_member()
async def revoke_used_invite(event: ChatMemberUpdated) -> None:
    """Make personalized invite links permanently single-use."""
    new_member = event.new_chat_member
    joined = new_member.status in (
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.MEMBER,
    ) or (
        new_member.status == ChatMemberStatus.RESTRICTED
        and bool(getattr(new_member, "is_member", False))
    )

    if not joined or event.invite_link is None:
        return

    revoked = await revoke_invite_link(
        event.bot,
        event.invite_link.invite_link,
    )
    if revoked:
        await db.update_invite_link(new_member.user.id, None)
        await db.clear_trial_invite_link(new_member.user.id)


@router.callback_query(F.data == "join_vip")
async def join_vip(call: CallbackQuery, state: FSMContext) -> None:
    try:
        telegram_id = call.from_user.id
        is_active = await db.is_user_active(telegram_id)

        if is_active:
            already_in_channel = await is_member(call.bot, telegram_id)
            if already_in_channel:
                await call.message.answer(msg.ALREADY_VIP)
                return

            user = await db.get_user(telegram_id)
            old_link = user["invite_link"] if user else None
            if old_link:
                revoked = await revoke_invite_link(call.bot, old_link)
                if not revoked:
                    await call.message.answer(msg.ERROR_GENERIC)
                    return
            invite_link = await create_invite_link(call.bot)
            await db.update_invite_link(telegram_id, invite_link)
            await call.message.answer(
                msg.INVITE_RESENT.format(invite_link=invite_link)
            )
            return

        await state.set_state(JoinVIP.waiting_uid)
        minimum_balance = await db.get_minimum_balance()
        await call.message.answer(
            msg.ASK_UID.format(
                register_link=REGISTER_LINK,
                min_balance=minimum_balance,
            )
        )

    except Exception:
        logger.exception("join_vip handler error")
        await call.message.answer(msg.ERROR_GENERIC)
    finally:
        await call.answer()


@router.message(JoinVIP.waiting_uid)
async def receive_uid(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    uid = (message.text or "").strip()
    if uid.startswith("/"):
        return

    if not validate_uid(uid):
        await message.answer(
            msg.UID_INVALID.format(
                min_length=UID_MIN_LENGTH,
                max_length=UID_MAX_LENGTH,
            )
        )
        return

    await message.answer(msg.CHECKING)

    async with _lock_for(message.from_user.id):
        await _register_uid(message, state, uid)


async def _register_uid(
    message: Message,
    state: FSMContext,
    uid: str,
) -> None:
    telegram_id = message.from_user.id
    invite_link = None
    active_trial = None

    try:
        active_trial = await db.get_active_trial(telegram_id)
        is_active = await db.is_user_active(telegram_id)
        if is_active:
            await message.answer(msg.ALREADY_VIP)
            await state.clear()
            return
    except Exception:
        logger.exception("Duplicate check DB error")
        await message.answer(msg.ERROR_DB)
        await state.clear()
        return

    try:
        result = await yubit.validate_user(uid)
    except Exception:
        logger.exception("API validation error")
        await message.answer(msg.ERROR_API)
        await state.clear()
        return

    if not result["success"]:
        logger.warning(
            "Validation failed for uid=%s telegram_id=%s: %s",
            uid,
            telegram_id,
            result.get("message"),
        )
        await message.answer(msg.VALIDATION_FAILED)
        await state.clear()
        return

    balance: float = result["balance"]
    minimum_balance = await db.get_minimum_balance()

    if is_insufficient_balance(balance, minimum_balance):
        await message.answer(
            msg.INSUFFICIENT_BALANCE.format(
                min_balance=minimum_balance,
                balance=balance,
            )
        )
        await state.clear()
        return

    try:
        invite_link = await create_invite_link(message.bot)
    except Exception:
        logger.exception("Invite link creation error")
        await message.answer(msg.ERROR_GENERIC)
        await state.clear()
        return

    try:
        status = await db.register_user(
            telegram_id=telegram_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            yubit_uid=uid,
            balance=balance,
            invite_link=invite_link,
        )
    except Exception:
        logger.exception("Database insert error")
        await revoke_invite_link(message.bot, invite_link)
        await message.answer(msg.ERROR_DB)
        await state.clear()
        return

    if status == "already_active":
        await revoke_invite_link(message.bot, invite_link)
        await message.answer(msg.ALREADY_VIP)
        await state.clear()
        return

    if status == "uid_taken":
        await revoke_invite_link(message.bot, invite_link)
        await message.answer(msg.UID_IN_USE)
        await state.clear()
        return

    if active_trial is not None and active_trial["invite_link"]:
        await revoke_invite_link(
            message.bot,
            active_trial["invite_link"],
        )

    logger.info(
        "User registered: telegram_id=%s uid=%s balance=%s status=%s",
        telegram_id,
        uid,
        balance,
        status,
    )

    await _send_success(
        message,
        uid,
        balance,
        invite_link,
        minimum_balance,
    )
    await state.clear()


@router.callback_query(F.data == "trial_vip")
async def trial_vip(call: CallbackQuery) -> None:
    invite_link = None
    registered = False
    try:
        telegram_id = call.from_user.id
        async with _lock_for(telegram_id):
            trial_state = await db.get_trial_state()
            if not trial_state["enabled"]:
                await call.message.answer(msg.TRIAL_INACTIVE)
                return

            if await db.is_user_active(telegram_id):
                await call.message.answer(msg.TRIAL_PAID_VIP)
                return

            active = await db.get_active_trial(telegram_id)
            if active is not None:
                invite_text = ""
                if active["invite_link"]:
                    invite_text = (
                        "\n\n🔗 لینک ورود:\n"
                        f"{active['invite_link']}"
                    )
                await call.message.answer(
                    msg.TRIAL_ALREADY_ACTIVE.format(
                        invite_text=invite_text
                    )
                )
                return

            invite_link = await create_invite_link(
                call.bot,
                expire_seconds=60 * 60,
            )
            result = await db.register_trial(
                telegram_id=telegram_id,
                invite_link=invite_link,
            )
            if result != "created":
                await revoke_invite_link(call.bot, invite_link)
                if result == "disabled":
                    await call.message.answer(msg.TRIAL_INACTIVE)
                elif result == "active":
                    await call.message.answer(
                        msg.TRIAL_ALREADY_ACTIVE.format(
                            invite_text=""
                        )
                    )
                else:
                    await call.message.answer(msg.TRIAL_ALREADY_USED)
                return

            registered = True
            await call.message.answer(
                msg.TRIAL_SUCCESS.format(invite_link=invite_link)
            )
    except Exception:
        logger.exception("Trial VIP handler error")
        if invite_link and not registered:
            await revoke_invite_link(call.bot, invite_link)
        await call.message.answer(msg.ERROR_GENERIC)
    finally:
        await call.answer()


@router.callback_query(F.data == "status")
async def account_status(call: CallbackQuery) -> None:
    try:
        user = await db.get_user(call.from_user.id)
        if user is None:
            trial = await db.get_active_trial(call.from_user.id)
            if trial is not None:
                await call.message.answer(
                    msg.TRIAL_ALREADY_ACTIVE.format(invite_text="")
                )
                return
            await call.message.answer(msg.NOT_VIP)
            return

        live_balance = await yubit.get_balance(user["yubit_uid"])
        if live_balance is not None:
            await db.update_balance(
                call.from_user.id,
                live_balance,
                record_check=False,
            )

        await call.message.answer(
            msg.STATUS_INFO.format(
                uid=user["yubit_uid"],
                balance=(
                    live_balance
                    if live_balance is not None
                    else user["balance"]
                ),
                status=user["vip_status"],
                warning_count=user["warning_count"],
            )
        )
    except Exception:
        logger.exception("Status handler error")
        await call.message.answer(msg.ERROR_GENERIC)
    finally:
        await call.answer()


@router.callback_query(F.data == "campaign")
async def campaign(call: CallbackQuery) -> None:
    try:
        saved = await db.get_campaign()
        if saved is None:
            await call.message.answer(msg.CAMPAIGN_EMPTY)
            return
        await call.bot.copy_message(
            chat_id=call.from_user.id,
            from_chat_id=saved["source_chat_id"],
            message_id=saved["source_message_id"],
        )
    except Exception:
        logger.exception("Campaign handler error")
        await call.message.answer(msg.ERROR_GENERIC)
    finally:
        await call.answer()


@router.callback_query(F.data == "support")
async def support(call: CallbackQuery, state: FSMContext) -> None:
    try:
        await state.set_state(Support.waiting_message)
        await call.message.answer(msg.SUPPORT_PROMPT)
    except Exception:
        logger.exception("Support handler error")
        await call.message.answer(msg.ERROR_GENERIC)
    finally:
        await call.answer()


@router.message(Support.waiting_message)
async def receive_support_message(
    message: Message,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    delivered = 0
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "-"
    )
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                msg.SUPPORT_ADMIN_HEADER.format(
                    first_name=message.from_user.first_name or "-",
                    username=username,
                    telegram_id=message.from_user.id,
                ),
            )
            copied = await message.bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            await db.save_support_message(
                admin_chat_id=admin_id,
                admin_message_id=copied.message_id,
                user_telegram_id=message.from_user.id,
            )
            delivered += 1
        except Exception:
            logger.exception(
                "Support delivery failed for admin_id=%s",
                admin_id,
            )

    if delivered:
        await state.clear()
        await message.answer(msg.SUPPORT_RECEIVED)
    else:
        await message.answer(msg.SUPPORT_DELIVERY_FAILED)


@router.callback_query(F.data == "register")
async def register(call: CallbackQuery) -> None:
    try:
        await call.message.answer(
            msg.REGISTER_MSG.format(register_link=REGISTER_LINK)
        )
    except Exception:
        logger.exception("Register handler error")
        await call.message.answer(msg.ERROR_GENERIC)
    finally:
        await call.answer()
