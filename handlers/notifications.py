"""
Notification System for Bot Updates and Alerts
IMPORTANT: Automatic notifications go to ADMIN channel, NOT @iraq_7kmmy
@iraq_7kmmy is for MANUAL announcements only

This module now uses the ChannelManager for multi-channel support
"""
import os
import logging
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
from handlers.channel_manager import channel_manager

logger = logging.getLogger(__name__)

# Update channel configuration
# NOTE: This channel (@iraq_7kmmy) is for MANUAL announcements only
# Automatic notifications go to ADMIN_CHANNEL_ID
UPDATE_CHANNEL_USERNAME = "@iraq_7kmmy"  # https://t.me/iraq_7kmmy


async def send_startup_notification(bot: Bot):
    """
    Send startup notification to ADMIN channel and logs channel
    Called when bot successfully starts

    NOTE: Does NOT send to @iraq_7kmmy (that's for manual announcements)
    """
    try:
        # Send to admin channel using channel manager
        await channel_manager.notify_bot_startup(bot)

        # Also log to logs channel
        await channel_manager.log_bot_startup(bot)

        logger.info("✅ Startup notification sent to Admin and Logs channels")
        return True

    except TelegramError as e:
        logger.warning(f"⚠️ Failed to send startup notification: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending startup notification: {e}")
        return False


async def send_shutdown_notification(bot: Bot, reason: str = "Normal shutdown"):
    """
    Send shutdown notification to ADMIN channel and logs channel

    Args:
        bot: Telegram Bot instance
        reason: Reason for shutdown (e.g., "Manual stop", "Error")

    NOTE: Does NOT send to @iraq_7kmmy (that's for manual announcements)
    """
    try:
        # Send to admin channel
        await channel_manager.notify_bot_shutdown(bot, reason)

        # Also log to logs channel
        await channel_manager.log_bot_shutdown(bot, reason)

        logger.info("✅ Shutdown notification sent to Admin and Logs channels")
        return True

    except TelegramError as e:
        logger.warning(f"⚠️ Failed to send shutdown notification: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending shutdown notification: {e}")
        return False


async def send_error_notification(bot: Bot, error_type: str, error_message: str):
    """
    Send error notification to ADMIN channel and logs channel

    Args:
        bot: Telegram Bot instance
        error_type: Type of error (e.g., "Download Error", "Database Error")
        error_message: Detailed error message

    NOTE: Does NOT send to @iraq_7kmmy (that's for manual announcements)
    """
    try:
        # Log to logs channel
        await channel_manager.log_error(bot, error_type, error_message)

        # Send critical errors to admin channel
        await channel_manager.notify_critical_error(bot, error_type, error_message)

        logger.info("✅ Error notification sent to Admin and Logs channels")
        return True

    except TelegramError as e:
        logger.warning(f"⚠️ Failed to send error notification: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending error notification: {e}")
        return False


async def send_update_notification(bot: Bot, version: str = "Latest", features: list = None):
    """
    Send update notification to @iraq_7kmmy

    WARNING: This is for MANUAL use only!
    This will post to the public @iraq_7kmmy channel

    Args:
        bot: Telegram Bot instance
        version: Version number or identifier
        features: List of new features
    """
    try:
        if not features:
            features = [
                "تحسينات في الأداء",
                "إصلاح أخطاء",
                "تحديثات أمنية"
            ]

        # This sends to @iraq_7kmmy - MANUAL only!
        logger.warning(f"⚠️ MANUAL announcement to @iraq_7kmmy channel - Version: {version}")
        await channel_manager.announce_update(bot, version, features)

        logger.info(f"✅ Manual update announcement sent to {UPDATE_CHANNEL_USERNAME}")
        return True

    except TelegramError as e:
        logger.warning(f"⚠️ Failed to send update notification: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending update notification: {e}")
        return False


async def announce_new_bot(bot: Bot, bot_name: str, bot_username: str, description: str):
    """
    Announce a new bot to the update channel

    Args:
        bot: Telegram Bot instance
        bot_name: Name of the new bot
        bot_username: Username of the new bot
        description: Description of the bot's features
    """
    try:
        message = (
            "🤖 **بوت جديد متاح / New Bot Available**\n\n"
            f"📱 **الاسم / Name:** {bot_name}\n"
            f"🔗 **Username:** @{bot_username}\n\n"
            f"📝 **الوصف / Description:**\n{description}\n\n"
            "✨ جربه الآن!"
        )

        await bot.send_message(
            chat_id=UPDATE_CHANNEL_USERNAME,
            text=message,
            parse_mode='Markdown'
        )

        logger.info(f"✅ New bot announcement sent to {UPDATE_CHANNEL_USERNAME}")
        return True

    except TelegramError as e:
        logger.warning(f"⚠️ Failed to send bot announcement: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending bot announcement: {e}")
        return False
