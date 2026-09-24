from datetime import datetime
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    CHECK_INTERVAL_DAYS,
    logger,
)
from constants import messages as msg
from database.database import db
from services.channel import remove_user, revoke_invite_link
from services.yubit_api import yubit
from services.telegram_retry import with_telegram_retry
from services.vip_rules import (
    MAX_BALANCE_WARNINGS,
    is_insufficient_balance,
    needs_recheck,
    should_remove_after_warnings,
)

scheduler = AsyncIOScheduler()


async def _safe_send(bot: Bot, telegram_id: int, text: str) -> None:
    try:
        await with_telegram_retry(
            lambda: bot.send_message(telegram_id, text)
        )
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.warning(
            "Failed to send message to %s: %s",
            telegram_id,
            exc,
        )
    except Exception:
        logger.exception(
            "Unexpected send error to %s",
            telegram_id,
        )


async def weekly_check(bot: Bot) -> None:
    """
    Recheck active VIP users.

    - Skip users checked within CHECK_INTERVAL_DAYS.
    - Kick only after a successful channel removal (or if already gone).
    - Join and kick both use the database minimum-balance setting.
    """
    logger.info("Weekly checker started.")

    try:
        users = await db.get_all_active_users()
    except Exception:
        logger.exception("Failed to fetch active users")
        return

    if not users:
        logger.info("No active users found. Checker finished.")
        return

    try:
        minimum_balance = await db.get_minimum_balance()
    except Exception:
        logger.exception("Failed to fetch minimum balance setting")
        return
    total = len(users)
    processed = 0
    warned = 0
    kicked = 0
    skipped = 0

    for user in users:
        telegram_id: int = user["telegram_id"]
        uid: str = user["yubit_uid"]

        try:
            if not needs_recheck(user["last_check"], CHECK_INTERVAL_DAYS):
                skipped += 1
                continue

            balance: Optional[float] = await yubit.get_balance(uid)

            if balance is None:
                logger.warning(
                    "Could not fetch balance for telegram_id=%s uid=%s. Skipping.",
                    telegram_id,
                    uid,
                )
                continue

            await db.update_balance(telegram_id, balance)
            processed += 1

            if is_insufficient_balance(balance, minimum_balance):
                warning_count = int(user["warning_count"] or 0)
                if not should_remove_after_warnings(warning_count):
                    next_warning = warning_count + 1
                    await db.add_warning(telegram_id)
                    warned += 1
                    logger.warning(
                        "Low-balance warning %s/%s: "
                        "telegram_id=%s balance=%s minimum=%s",
                        next_warning,
                        MAX_BALANCE_WARNINGS,
                        telegram_id,
                        balance,
                        minimum_balance,
                    )
                    await _safe_send(
                        bot,
                        telegram_id,
                        msg.WARNING_MSG.format(
                            warning_count=next_warning,
                            balance=balance,
                            min_balance=minimum_balance,
                        ),
                    )
                    continue

                invite_link = user["invite_link"]
                if invite_link:
                    revoked = await revoke_invite_link(bot, invite_link)
                    if not revoked:
                        logger.error(
                            "Invite revocation failed for telegram_id=%s; "
                            "leaving user active.",
                            telegram_id,
                        )
                        continue

                removed = await remove_user(bot, telegram_id)
                if not removed:
                    logger.error(
                        "Kick failed for telegram_id=%s; leaving user active.",
                        telegram_id,
                    )
                    continue

                await db.update_invite_link(telegram_id, None)
                await db.deactivate_user(telegram_id)
                kicked += 1
                logger.info(
                    "User kicked: telegram_id=%s balance=%s < %s",
                    telegram_id,
                    balance,
                    minimum_balance,
                )
                await _safe_send(
                    bot,
                    telegram_id,
                    msg.KICK_MSG.format(
                        balance=balance,
                        min_balance=minimum_balance,
                    ),
                )
                continue

        except Exception:
            logger.exception(
                "Checker error for telegram_id=%s. Continuing.",
                telegram_id,
            )
            continue

    logger.info(
        "Weekly checker finished. Total=%s Processed=%s "
        "Skipped=%s Warned=%s Kicked=%s.",
        total,
        processed,
        skipped,
        warned,
        kicked,
    )


async def expire_trials(bot: Bot) -> None:
    try:
        trials = await db.get_expired_trials()
    except Exception:
        logger.exception("Failed to fetch expired VIP trials")
        return

    for trial in trials:
        telegram_id = int(trial["telegram_id"])
        generation = int(trial["generation"])
        try:
            if await db.is_user_active(telegram_id):
                await db.mark_trial_expired(telegram_id, generation)
                continue

            invite_link = trial["invite_link"]
            if invite_link:
                revoked = await revoke_invite_link(bot, invite_link)
                if not revoked:
                    continue

            removed = await remove_user(bot, telegram_id)
            if not removed:
                continue

            await db.mark_trial_expired(telegram_id, generation)
            await _safe_send(bot, telegram_id, msg.TRIAL_EXPIRED)
            logger.info(
                "VIP trial expired: telegram_id=%s generation=%s",
                telegram_id,
                generation,
            )
        except Exception:
            logger.exception(
                "Trial expiry failed for telegram_id=%s",
                telegram_id,
            )


def start_scheduler(bot: Bot) -> None:
    scheduler.add_job(
        weekly_check,
        "interval",
        days=CHECK_INTERVAL_DAYS,
        args=[bot],
        id="weekly_checker",
        replace_existing=True,
        next_run_time=datetime.now(),
    )
    scheduler.add_job(
        expire_trials,
        "interval",
        minutes=1,
        args=[bot],
        id="trial_expiry_checker",
        replace_existing=True,
        next_run_time=datetime.now(),
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started. Interval: every %s day(s). First run is immediate.",
        CHECK_INTERVAL_DAYS,
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
