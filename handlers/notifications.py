"""
Notification System for Bot Updates and Alerts
Sends notifications to the update channel (@iraq_7kmmy)
"""
import os
import logging
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

# Update channel configuration
UPDATE_CHANNEL_USERNAME = "@iraq_7kmmy"  # https://t.me/iraq_7kmmy


async def send_startup_notification(bot: Bot):
    """
    Send startup notification to update channel
    Called when bot successfully starts
    """
    try:
        timestamp = datetime.now().strftime("%H:%M — %d-%m-%Y")

        message = (
            "🚀 **تم تشغيل البوت بنجاح / Bot Started Successfully**\n\n"
            "✅ **جميع الأنظمة تعمل / All Systems Operational**\n\n"
            "🎯 **المميزات النشطة / Active Features:**\n"
            "• تحميل فيديوهات من +1000 موقع\n"
            "• نظام اختيار فيديوهات محددة من القوائم\n"
            "• تتبع دقيق للتقدم (1%)\n"
            "• تفاعلات تلقائية 👀\n"
            "• نظام الإحالة والمكافآت\n\n"
            f"🕒 **الوقت / Time:** {timestamp}\n"
            "⚡ **الحالة / Status:** جاهز للاستخدام"
        )

        await bot.send_message(
            chat_id=UPDATE_CHANNEL_USERNAME,
            text=message,
            parse_mode='Markdown'
        )

        logger.info(f"✅ Startup notification sent to {UPDATE_CHANNEL_USERNAME}")
        return True

    except TelegramError as e:
        logger.warning(f"⚠️ Failed to send startup notification: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending startup notification: {e}")
        return False


async def send_shutdown_notification(bot: Bot, reason: str = "Normal shutdown"):
    """
    Send shutdown notification to update channel

    Args:
        bot: Telegram Bot instance
        reason: Reason for shutdown (e.g., "Manual stop", "Error")
    """
    try:
        timestamp = datetime.now().strftime("%H:%M — %d-%m-%Y")

        message = (
            "⏹️ **توقف البوت / Bot Stopped**\n\n"
            f"📝 **السبب / Reason:** {reason}\n"
            f"🕒 **الوقت / Time:** {timestamp}\n\n"
            "🔄 سيتم إعادة التشغيل قريباً..."
        )

        await bot.send_message(
            chat_id=UPDATE_CHANNEL_USERNAME,
            text=message,
            parse_mode='Markdown'
        )

        logger.info(f"✅ Shutdown notification sent to {UPDATE_CHANNEL_USERNAME}")
        return True

    except TelegramError as e:
        logger.warning(f"⚠️ Failed to send shutdown notification: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending shutdown notification: {e}")
        return False


async def send_error_notification(bot: Bot, error_type: str, error_message: str):
    """
    Send error notification to update channel

    Args:
        bot: Telegram Bot instance
        error_type: Type of error (e.g., "Download Error", "Database Error")
        error_message: Detailed error message
    """
    try:
        timestamp = datetime.now().strftime("%H:%M — %d-%m-%Y")

        # Truncate long error messages
        if len(error_message) > 200:
            error_message = error_message[:200] + "..."

        message = (
            "❌ **تنبيه خطأ / Error Alert**\n\n"
            f"🔴 **النوع / Type:** {error_type}\n"
            f"📝 **التفاصيل / Details:**\n`{error_message}`\n\n"
            f"🕒 **الوقت / Time:** {timestamp}\n"
            "🔧 جاري التحقق والإصلاح..."
        )

        await bot.send_message(
            chat_id=UPDATE_CHANNEL_USERNAME,
            text=message,
            parse_mode='Markdown'
        )

        logger.info(f"✅ Error notification sent to {UPDATE_CHANNEL_USERNAME}")
        return True

    except TelegramError as e:
        logger.warning(f"⚠️ Failed to send error notification: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending error notification: {e}")
        return False


async def send_update_notification(bot: Bot, version: str = "Latest", features: list = None):
    """
    Send update notification to update channel

    Args:
        bot: Telegram Bot instance
        version: Version number or identifier
        features: List of new features
    """
    try:
        timestamp = datetime.now().strftime("%H:%M — %d-%m-%Y")

        features_text = ""
        if features:
            for feature in features:
                features_text += f"• {feature}\n"
        else:
            features_text = (
                "• تحسينات في الأداء\n"
                "• إصلاح أخطاء\n"
                "• تحديثات أمنية"
            )

        message = (
            "🎉 **تحديث جديد متاح / New Update Available**\n\n"
            f"📦 **الإصدار / Version:** {version}\n\n"
            "✨ **المميزات الجديدة / New Features:**\n"
            f"{features_text}\n"
            f"🕒 **تاريخ التحديث / Update Date:** {timestamp}\n\n"
            "🚀 التحديث مفعّل الآن!"
        )

        await bot.send_message(
            chat_id=UPDATE_CHANNEL_USERNAME,
            text=message,
            parse_mode='Markdown'
        )

        logger.info(f"✅ Update notification sent to {UPDATE_CHANNEL_USERNAME}")
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
