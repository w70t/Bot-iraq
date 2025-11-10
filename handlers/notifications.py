"""
نظام الإشعارات التلقائية لقناة التحديثات
Automatic Notification System for Update Channel
"""

import os
import logging
from datetime import datetime
from telegram import Bot
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# قناة التحديثات الرسمية
UPDATE_CHANNEL = "@iraq_7kmmy"  # https://t.me/iraq_7kmmy

def get_bot_name():
    """جلب اسم البوت من متغيرات البيئة"""
    return os.getenv("BOT_NAME", "Iraq Download Bot")

def get_bot_version():
    """جلب إصدار البوت من git أو من متغيرات البيئة"""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()[:7]
    except Exception:
        pass
    return os.getenv("BOT_VERSION", "v1.0")

async def send_startup_notification(bot: Bot):
    """
    إرسال إشعار تشغيل البوت
    Send bot startup notification
    """
    try:
        bot_name = get_bot_name()
        version = get_bot_version()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = (
            "🚀 **تم تشغيل البوت بنجاح!**\n"
            "**Bot Started Successfully!**\n\n"
            f"📦 الاسم / Name: `{bot_name}`\n"
            f"🔗 الإصدار / Version: `{version}`\n"
            f"🕒 التاريخ / Date: `{timestamp}`\n"
            f"⚡ الحالة / Status: **Online**\n\n"
            "✅ جميع الأنظمة تعمل بشكل طبيعي\n"
            "✅ All systems operational"
        )

        await bot.send_message(
            chat_id=UPDATE_CHANNEL,
            text=message,
            parse_mode="Markdown"
        )

        logger.info(f"✅ تم إرسال إشعار التشغيل إلى {UPDATE_CHANNEL}")
        return True

    except Exception as e:
        logger.warning(f"⚠️ فشل إرسال إشعار التشغيل: {e}")
        return False

async def send_shutdown_notification(bot: Bot, reason: str = "عادي"):
    """
    إرسال إشعار إيقاف البوت
    Send bot shutdown notification
    """
    try:
        bot_name = get_bot_name()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = (
            "⏸️ **تم إيقاف البوت**\n"
            "**Bot Stopped**\n\n"
            f"📦 الاسم / Name: `{bot_name}`\n"
            f"🕒 الوقت / Time: `{timestamp}`\n"
            f"📝 السبب / Reason: `{reason}`\n\n"
            "⚠️ البوت متوقف مؤقتاً\n"
            "⚠️ Bot temporarily stopped"
        )

        await bot.send_message(
            chat_id=UPDATE_CHANNEL,
            text=message,
            parse_mode="Markdown"
        )

        logger.info(f"✅ تم إرسال إشعار الإيقاف إلى {UPDATE_CHANNEL}")
        return True

    except Exception as e:
        logger.warning(f"⚠️ فشل إرسال إشعار الإيقاف: {e}")
        return False

async def send_error_notification(bot: Bot, error_type: str, error_message: str):
    """
    إرسال إشعار عند حدوث خطأ عام
    Send notification when critical error occurs
    """
    try:
        bot_name = get_bot_name()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Truncate error message if too long
        error_short = error_message[:200] if len(error_message) > 200 else error_message

        message = (
            "⚠️ **تنبيه: حدث خطأ في النظام**\n"
            "**Alert: System Error Occurred**\n\n"
            f"📦 البوت / Bot: `{bot_name}`\n"
            f"🕒 الوقت / Time: `{timestamp}`\n"
            f"🔴 نوع الخطأ / Error Type: `{error_type}`\n"
            f"📝 التفاصيل / Details:\n```\n{error_short}\n```\n\n"
            "🔧 يتم معالجة المشكلة...\n"
            "🔧 Handling the issue..."
        )

        await bot.send_message(
            chat_id=UPDATE_CHANNEL,
            text=message,
            parse_mode="Markdown"
        )

        logger.info(f"✅ تم إرسال إشعار الخطأ إلى {UPDATE_CHANNEL}")
        return True

    except Exception as e:
        logger.warning(f"⚠️ فشل إرسال إشعار الخطأ: {e}")
        return False

async def send_update_notification(bot: Bot, update_details: str):
    """
    إرسال إشعار تحديث البوت
    Send bot update notification
    """
    try:
        bot_name = get_bot_name()
        version = get_bot_version()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = (
            "🔄 **تم تحديث البوت بنجاح!**\n"
            "**Bot Updated Successfully!**\n\n"
            f"📦 البوت / Bot: `{bot_name}`\n"
            f"🔗 الإصدار / Version: `{version}`\n"
            f"🕒 التاريخ / Date: `{timestamp}`\n\n"
            f"🎯 **التحديثات / Updates:**\n{update_details}\n\n"
            "✅ التحديث مكتمل والبوت جاهز\n"
            "✅ Update complete and bot ready"
        )

        await bot.send_message(
            chat_id=UPDATE_CHANNEL,
            text=message,
            parse_mode="Markdown"
        )

        logger.info(f"✅ تم إرسال إشعار التحديث إلى {UPDATE_CHANNEL}")
        return True

    except Exception as e:
        logger.warning(f"⚠️ فشل إرسال إشعار التحديث: {e}")
        return False

async def announce_new_bot(bot: Bot, new_bot_name: str, new_bot_username: str = None):
    """
    إعلان إضافة بوت جديد إلى الشبكة
    Announce new bot addition to the network
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        bot_link = f"@{new_bot_username}" if new_bot_username else new_bot_name

        message = (
            "✨ **بوت جديد انضم إلى الشبكة!**\n"
            "**New Bot Joined the Network!**\n\n"
            f"🤖 الاسم / Name: `{new_bot_name}`\n"
            f"🔗 الرابط / Link: {bot_link}\n"
            f"🕒 التاريخ / Date: `{timestamp}`\n\n"
            "🛠️ تمت إضافته بنجاح إلى النظام\n"
            "🛠️ Successfully added to the system\n\n"
            "🎉 مرحباً بالعضو الجديد!"
        )

        await bot.send_message(
            chat_id=UPDATE_CHANNEL,
            text=message,
            parse_mode="Markdown"
        )

        logger.info(f"✅ تم إرسال إعلان البوت الجديد إلى {UPDATE_CHANNEL}")
        return True

    except Exception as e:
        logger.warning(f"⚠️ فشل إرسال إعلان البوت الجديد: {e}")
        return False

async def send_stats_notification(bot: Bot, stats: dict):
    """
    إرسال إحصائيات دورية
    Send periodic statistics
    """
    try:
        bot_name = get_bot_name()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        total_users = stats.get('total_users', 0)
        total_downloads = stats.get('total_downloads', 0)
        active_users = stats.get('active_users', 0)

        message = (
            "📊 **تقرير إحصائيات البوت**\n"
            "**Bot Statistics Report**\n\n"
            f"📦 البوت / Bot: `{bot_name}`\n"
            f"🕒 التاريخ / Date: `{timestamp}`\n\n"
            f"👥 إجمالي المستخدمين / Total Users: `{total_users}`\n"
            f"⚡ المستخدمون النشطون / Active Users: `{active_users}`\n"
            f"📥 إجمالي التحميلات / Total Downloads: `{total_downloads}`\n\n"
            "✅ النظام يعمل بكفاءة\n"
            "✅ System running efficiently"
        )

        await bot.send_message(
            chat_id=UPDATE_CHANNEL,
            text=message,
            parse_mode="Markdown"
        )

        logger.info(f"✅ تم إرسال تقرير الإحصائيات إلى {UPDATE_CHANNEL}")
        return True

    except Exception as e:
        logger.warning(f"⚠️ فشل إرسال تقرير الإحصائيات: {e}")
        return False
