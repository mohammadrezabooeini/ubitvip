import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
)

from database.database import Database, db
from services.yubit_api import YubitAPI, yubit
from services.telegram_retry import with_telegram_retry


@dataclass
class BalanceRefreshResult:
    checked: int = 0
    failed: int = 0
    below_minimum: int = 0
    users: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BroadcastResult:
    total: int = 0
    sent: int = 0
    failed: int = 0


async def refresh_all_vip_balances(
    minimum_balance: float,
    database: Database = db,
    api: YubitAPI = yubit,
    concurrency: int = 5,
) -> BalanceRefreshResult:
    users = await database.get_all_active_users()
    result = BalanceRefreshResult()
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def refresh(user: Any) -> Dict[str, Any]:
        async with semaphore:
            balance = await api.get_balance(user["yubit_uid"])
            if balance is None:
                return {
                    "ok": False,
                    "telegram_id": user["telegram_id"],
                    "uid": user["yubit_uid"],
                    "first_name": user["first_name"],
                }

            await database.update_balance(
                user["telegram_id"],
                balance,
                record_check=False,
            )
            return {
                "ok": True,
                "telegram_id": user["telegram_id"],
                "uid": user["yubit_uid"],
                "first_name": user["first_name"],
                "balance": balance,
                "below_minimum": balance < minimum_balance,
            }

    refreshed = await asyncio.gather(
        *(refresh(user) for user in users),
        return_exceptions=True,
    )

    for item in refreshed:
        if isinstance(item, Exception):
            result.failed += 1
            continue
        if not item["ok"]:
            result.failed += 1
            result.users.append(item)
            continue

        result.checked += 1
        if item["below_minimum"]:
            result.below_minimum += 1
        result.users.append(item)

    return result


async def broadcast_copy(
    bot: Bot,
    user_ids: Iterable[int],
    from_chat_id: int,
    message_id: int,
) -> BroadcastResult:
    recipients = list(dict.fromkeys(user_ids))
    result = BroadcastResult(total=len(recipients))

    for telegram_id in recipients:
        try:
            await with_telegram_retry(
                lambda telegram_id=telegram_id: bot.copy_message(
                    chat_id=telegram_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id,
                ),
                attempts=3,
            )
            result.sent += 1
        except (TelegramBadRequest, TelegramForbiddenError):
            result.failed += 1
        except Exception:
            result.failed += 1

    return result


async def broadcast_text(
    bot: Bot,
    user_ids: Iterable[int],
    text: str,
) -> BroadcastResult:
    recipients = list(dict.fromkeys(user_ids))
    result = BroadcastResult(total=len(recipients))

    for telegram_id in recipients:
        try:
            await with_telegram_retry(
                lambda telegram_id=telegram_id: bot.send_message(
                    chat_id=telegram_id,
                    text=text,
                ),
                attempts=3,
            )
            result.sent += 1
        except (TelegramBadRequest, TelegramForbiddenError):
            result.failed += 1
        except Exception:
            result.failed += 1

    return result
