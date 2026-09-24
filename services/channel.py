import time

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
)

from config import CHANNEL_ID, INVITE_EXPIRE_SECONDS, logger
from services.telegram_retry import with_telegram_retry


class ChannelManager:
    def __init__(self, channel_id: str = CHANNEL_ID) -> None:
        self.channel_id: str = channel_id

    async def create_invite_link(
        self,
        bot: Bot,
        expire_seconds: int | None = None,
    ) -> str:
        """Create a one-time invite that expires with the check interval."""
        lifetime = (
            INVITE_EXPIRE_SECONDS
            if expire_seconds is None
            else expire_seconds
        )

        async def _create():
            return await bot.create_chat_invite_link(
                chat_id=self.channel_id,
                member_limit=1,
                expire_date=int(time.time()) + lifetime,
                creates_join_request=False,
            )

        try:
            invite = await with_telegram_retry(_create)
            logger.info("New invite link created.")
            return invite.invite_link
        except (TelegramBadRequest, TelegramForbiddenError):
            logger.exception("Create invite link failed")
            raise
        except Exception:
            logger.exception("Unexpected error creating invite link")
            raise

    async def revoke_invite_link(self, bot: Bot, invite_link: str) -> bool:
        async def _revoke():
            return await bot.revoke_chat_invite_link(
                chat_id=self.channel_id,
                invite_link=invite_link,
            )

        try:
            await with_telegram_retry(_revoke)
            logger.info("Invite link revoked after use.")
            return True
        except TelegramBadRequest as exc:
            if "invite hash expired" in str(exc).lower():
                return True
            logger.warning(
                "Failed to revoke invite link: %s",
                exc,
            )
            return False
        except Exception:
            logger.warning(
                "Failed to revoke invite link",
                exc_info=True,
            )
            return False

    async def remove_user(self, bot: Bot, telegram_id: int) -> bool:
        """Kick a user with ban then unban. Missing users count as success."""

        async def _ban():
            return await bot.ban_chat_member(
                chat_id=self.channel_id,
                user_id=telegram_id,
            )

        async def _unban():
            return await bot.unban_chat_member(
                chat_id=self.channel_id,
                user_id=telegram_id,
                only_if_banned=True,
            )

        try:
            await with_telegram_retry(_ban)
            await with_telegram_retry(_unban)
            logger.info("User removed from channel: %s", telegram_id)
            return True

        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            text = str(exc).lower()
            if any(
                token in text
                for token in (
                    "user not found",
                    "not a participant",
                    "user_not_participant",
                    "chat_member_not_found",
                    "participant_id_invalid",
                )
            ):
                logger.info(
                    "User %s is not in the channel; treating kick as success.",
                    telegram_id,
                )
                return True

            logger.warning("Remove user failed (telegram): %s", exc)
            return False

        except Exception:
            logger.exception(
                "Unexpected error removing user %s",
                telegram_id,
            )
            return False

    async def is_member(self, bot: Bot, telegram_id: int) -> bool:
        try:
            member = await with_telegram_retry(
                lambda: bot.get_chat_member(
                    self.channel_id,
                    telegram_id,
                )
            )
            status = member.status
            if status in (
                ChatMemberStatus.CREATOR,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.MEMBER,
                "creator",
                "administrator",
                "member",
            ):
                return True
            if status in (ChatMemberStatus.RESTRICTED, "restricted"):
                return bool(getattr(member, "is_member", False))
            return False

        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            logger.warning("is_member check failed: %s", exc)
            return False
        except Exception:
            logger.exception("Unexpected error in is_member")
            return False

    async def check_bot_permissions(self, bot: Bot) -> bool:
        try:
            me = await bot.get_me()
            member = await bot.get_chat_member(
                self.channel_id,
                me.id,
            )

            if member.status not in (
                ChatMemberStatus.ADMINISTRATOR,
                "administrator",
            ):
                logger.warning(
                    "Bot is not an administrator in the channel."
                )
                return False

            if not getattr(member, "can_invite_users", False):
                logger.warning(
                    "Bot lacks can_invite_users permission."
                )
                return False

            if not getattr(member, "can_restrict_members", False):
                logger.warning(
                    "Bot lacks can_restrict_members permission."
                )
                return False

            return True

        except Exception:
            logger.exception("Bot permission check error")
            return False


channel = ChannelManager()

create_invite_link = channel.create_invite_link
revoke_invite_link = channel.revoke_invite_link
remove_user = channel.remove_user
is_member = channel.is_member
check_bot_permissions = channel.check_bot_permissions
