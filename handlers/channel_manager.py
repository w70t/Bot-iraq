"""
Channel Manager System
نظام إدارة القنوات للبوت

This module manages all bot channels:
1. Logs Channel - For bot events and errors
2. Videos Channel - For downloaded videos backup
3. New Users Channel - For new user registrations
4. Statistics Channel - For daily statistics
5. Updates Channel - For announcements and updates
"""

import os
import logging
from datetime import datetime
from typing import Optional, Union
from telegram import Bot, InputMediaVideo, InputMediaPhoto
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class ChannelManager:
    """Manages all bot notification channels"""

    def __init__(self):
        """Initialize channel manager with channel IDs from environment"""
        self.log_channel = os.getenv("LOG_CHANNEL_ID")
        self.videos_channel = os.getenv("VIDEOS_CHANNEL_ID")
        self.new_users_channel = os.getenv("NEW_USERS_CHANNEL_ID")
        self.stats_channel = os.getenv("STATS_CHANNEL_ID")
        self.updates_channel = os.getenv("UPDATES_CHANNEL_USERNAME", "@iraq_7kmmy")

        # Log which channels are configured
        self._log_configuration()

    def _log_configuration(self):
        """Log which channels are configured"""
        channels_status = {
            "Logs": "✅" if self.log_channel else "❌",
            "Videos": "✅" if self.videos_channel else "❌",
            "New Users": "✅" if self.new_users_channel else "❌",
            "Statistics": "✅" if self.stats_channel else "❌",
            "Updates": "✅" if self.updates_channel else "❌"
        }
        logger.info(f"Channel Manager Configuration: {channels_status}")

    def _get_timestamp(self) -> str:
        """Get formatted timestamp"""
        return datetime.now().strftime("%H:%M — %d-%m-%Y")

    async def _send_message(
        self,
        bot: Bot,
        channel_id: Optional[str],
        message: str,
        channel_name: str = "channel",
        parse_mode: str = 'Markdown',
        disable_notification: bool = False
    ) -> bool:
        """
        Internal method to send message to a channel

        Args:
            bot: Telegram Bot instance
            channel_id: Channel ID or username
            message: Message text
            channel_name: Name of channel for logging
            parse_mode: Message parse mode
            disable_notification: Whether to send silently

        Returns:
            bool: True if successful, False otherwise
        """
        if not channel_id:
            logger.debug(f"⚠️ {channel_name} channel not configured, skipping notification")
            return False

        try:
            await bot.send_message(
                chat_id=channel_id,
                text=message,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
            logger.info(f"✅ Message sent to {channel_name} channel ({channel_id})")
            return True

        except TelegramError as e:
            logger.warning(f"⚠️ Failed to send to {channel_name} channel: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error sending to {channel_name} channel: {e}")
            return False

    # ═══════════════════════════════════════════════════════════
    # LOGS CHANNEL METHODS
    # ═══════════════════════════════════════════════════════════

    async def log_bot_startup(self, bot: Bot) -> bool:
        """
        Log bot startup to logs channel

        Args:
            bot: Telegram Bot instance

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()
        message = (
            "🚀 **تشغيل البوت / Bot Started**\n\n"
            "✅ **الحالة / Status:** جميع الأنظمة تعمل\n"
            f"🕒 **الوقت / Time:** {timestamp}\n"
            "⚡ **النوع / Type:** Startup Event"
        )
        return await self._send_message(bot, self.log_channel, message, "Logs")

    async def log_bot_shutdown(self, bot: Bot, reason: str = "Normal shutdown") -> bool:
        """
        Log bot shutdown to logs channel

        Args:
            bot: Telegram Bot instance
            reason: Shutdown reason

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()
        message = (
            "⏹️ **إيقاف البوت / Bot Stopped**\n\n"
            f"📝 **السبب / Reason:** {reason}\n"
            f"🕒 **الوقت / Time:** {timestamp}\n"
            "🔄 **الحالة / Status:** Stopped"
        )
        return await self._send_message(bot, self.log_channel, message, "Logs")

    async def log_error(
        self,
        bot: Bot,
        error_type: str,
        error_message: str,
        user_id: Optional[int] = None
    ) -> bool:
        """
        Log error to logs channel

        Args:
            bot: Telegram Bot instance
            error_type: Type of error
            error_message: Error message
            user_id: Optional user ID who triggered the error

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()

        # Truncate long error messages
        if len(error_message) > 300:
            error_message = error_message[:300] + "..."

        user_info = f"\n👤 **المستخدم / User ID:** `{user_id}`" if user_id else ""

        message = (
            "❌ **خطأ / Error Alert**\n\n"
            f"🔴 **النوع / Type:** {error_type}\n"
            f"📝 **التفاصيل / Details:**\n`{error_message}`"
            f"{user_info}\n"
            f"🕒 **الوقت / Time:** {timestamp}"
        )
        return await self._send_message(bot, self.log_channel, message, "Logs")

    async def log_download(
        self,
        bot: Bot,
        user_id: int,
        username: Optional[str],
        platform: str,
        url: str,
        success: bool = True
    ) -> bool:
        """
        Log download activity to logs channel

        Args:
            bot: Telegram Bot instance
            user_id: User ID
            username: Username
            platform: Platform (YouTube, Instagram, etc.)
            url: Video URL
            success: Whether download was successful

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()
        status = "✅ نجح" if success else "❌ فشل"
        user_mention = f"@{username}" if username else f"ID: {user_id}"

        # Truncate long URLs
        if len(url) > 100:
            url = url[:100] + "..."

        message = (
            f"📥 **تحميل جديد / New Download** {status}\n\n"
            f"👤 **المستخدم / User:** {user_mention}\n"
            f"📱 **المنصة / Platform:** {platform}\n"
            f"🔗 **الرابط / URL:** `{url}`\n"
            f"🕒 **الوقت / Time:** {timestamp}"
        )
        return await self._send_message(
            bot,
            self.log_channel,
            message,
            "Logs",
            disable_notification=True
        )

    # ═══════════════════════════════════════════════════════════
    # VIDEOS CHANNEL METHODS
    # ═══════════════════════════════════════════════════════════

    async def send_video_backup(
        self,
        bot: Bot,
        video_path: str,
        caption: str,
        thumbnail_path: Optional[str] = None
    ) -> bool:
        """
        Send video backup to videos channel

        Args:
            bot: Telegram Bot instance
            video_path: Path to video file
            caption: Video caption
            thumbnail_path: Optional thumbnail path

        Returns:
            bool: True if successful
        """
        if not self.videos_channel:
            logger.debug("⚠️ Videos channel not configured")
            return False

        try:
            with open(video_path, 'rb') as video:
                thumb = None
                if thumbnail_path and os.path.exists(thumbnail_path):
                    thumb = open(thumbnail_path, 'rb')

                await bot.send_video(
                    chat_id=self.videos_channel,
                    video=video,
                    caption=caption,
                    thumbnail=thumb,
                    disable_notification=True,
                    parse_mode='Markdown'
                )

                if thumb:
                    thumb.close()

            logger.info(f"✅ Video backup sent to videos channel")
            return True

        except Exception as e:
            logger.error(f"❌ Error sending video backup: {e}")
            return False

    async def log_video_stats(
        self,
        bot: Bot,
        total_downloads: int,
        today_downloads: int,
        most_popular_platform: str
    ) -> bool:
        """
        Send video statistics to videos channel

        Args:
            bot: Telegram Bot instance
            total_downloads: Total download count
            today_downloads: Today's download count
            most_popular_platform: Most popular platform

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()
        message = (
            "📊 **إحصائيات الفيديوهات / Video Statistics**\n\n"
            f"📥 **إجمالي التحميلات / Total:** {total_downloads:,}\n"
            f"📅 **اليوم / Today:** {today_downloads:,}\n"
            f"🏆 **الأكثر شعبية / Popular:** {most_popular_platform}\n"
            f"🕒 **التحديث / Updated:** {timestamp}"
        )
        return await self._send_message(
            bot,
            self.videos_channel,
            message,
            "Videos",
            disable_notification=True
        )

    # ═══════════════════════════════════════════════════════════
    # NEW USERS CHANNEL METHODS
    # ═══════════════════════════════════════════════════════════

    async def log_new_user(
        self,
        bot: Bot,
        user_id: int,
        username: Optional[str],
        first_name: str,
        language_code: Optional[str] = None,
        referrer_id: Optional[int] = None
    ) -> bool:
        """
        Log new user registration to new users channel

        Args:
            bot: Telegram Bot instance
            user_id: New user ID
            username: Username
            first_name: First name
            language_code: User's language code
            referrer_id: ID of user who referred them

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()
        user_mention = f"@{username}" if username else first_name
        lang = language_code or "Unknown"
        referral_info = f"\n🔗 **المُحيل / Referred by:** `{referrer_id}`" if referrer_id else ""

        message = (
            "🎉 **مستخدم جديد / New User**\n\n"
            f"👤 **الاسم / Name:** {user_mention}\n"
            f"🆔 **المعرف / ID:** `{user_id}`\n"
            f"🌐 **اللغة / Language:** {lang}"
            f"{referral_info}\n"
            f"🕒 **الانضمام / Joined:** {timestamp}"
        )
        return await self._send_message(
            bot,
            self.new_users_channel,
            message,
            "New Users",
            disable_notification=True
        )

    async def log_milestone(self, bot: Bot, milestone: int) -> bool:
        """
        Log user milestone achievement

        Args:
            bot: Telegram Bot instance
            milestone: Milestone number (100, 500, 1000, etc.)

        Returns:
            bool: True if successful
        """
        message = (
            "🎊 **إنجاز جديد / Milestone Reached!**\n\n"
            f"🎯 **عدد المستخدمين / Total Users:** {milestone:,}\n"
            "🚀 شكراً لدعمكم المتواصل!"
        )
        return await self._send_message(
            bot,
            self.new_users_channel,
            message,
            "New Users"
        )

    # ═══════════════════════════════════════════════════════════
    # STATISTICS CHANNEL METHODS
    # ═══════════════════════════════════════════════════════════

    async def send_daily_stats(
        self,
        bot: Bot,
        total_users: int,
        new_users_today: int,
        total_downloads: int,
        downloads_today: int,
        active_subscriptions: int,
        revenue_today: float = 0.0
    ) -> bool:
        """
        Send daily statistics report

        Args:
            bot: Telegram Bot instance
            total_users: Total user count
            new_users_today: New users today
            total_downloads: Total downloads
            downloads_today: Downloads today
            active_subscriptions: Active subscription count
            revenue_today: Revenue today

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()

        message = (
            "📊 **التقرير اليومي / Daily Report**\n"
            "═══════════════════════════════\n\n"
            "👥 **المستخدمون / Users:**\n"
            f"  • الإجمالي / Total: {total_users:,}\n"
            f"  • جديد اليوم / New Today: {new_users_today:,}\n\n"
            "📥 **التحميلات / Downloads:**\n"
            f"  • الإجمالي / Total: {total_downloads:,}\n"
            f"  • اليوم / Today: {downloads_today:,}\n\n"
            "💎 **الاشتراكات / Subscriptions:**\n"
            f"  • النشطة / Active: {active_subscriptions:,}\n"
        )

        if revenue_today > 0:
            message += f"\n💰 **الإيرادات اليوم / Revenue:** ${revenue_today:.2f}\n"

        message += f"\n🕒 **التاريخ / Date:** {timestamp}"

        return await self._send_message(bot, self.stats_channel, message, "Statistics")

    async def send_weekly_stats(
        self,
        bot: Bot,
        stats_data: dict
    ) -> bool:
        """
        Send weekly statistics report

        Args:
            bot: Telegram Bot instance
            stats_data: Dictionary with weekly stats

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()

        message = (
            "📈 **التقرير الأسبوعي / Weekly Report**\n"
            "═══════════════════════════════\n\n"
            f"📊 **الملخص / Summary:**\n"
            f"  • مستخدمين جدد / New Users: {stats_data.get('new_users', 0):,}\n"
            f"  • تحميلات / Downloads: {stats_data.get('downloads', 0):,}\n"
            f"  • اشتراكات جديدة / New Subs: {stats_data.get('new_subs', 0):,}\n\n"
            f"🕒 **الأسبوع / Week:** {timestamp}"
        )

        return await self._send_message(bot, self.stats_channel, message, "Statistics")

    # ═══════════════════════════════════════════════════════════
    # UPDATES CHANNEL METHODS
    # ═══════════════════════════════════════════════════════════

    async def announce_update(
        self,
        bot: Bot,
        version: str,
        features: list,
        improvements: Optional[list] = None
    ) -> bool:
        """
        Announce new update to updates channel

        Args:
            bot: Telegram Bot instance
            version: Version number
            features: List of new features
            improvements: List of improvements

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()

        features_text = "\n".join([f"  • {f}" for f in features])
        improvements_text = ""
        if improvements:
            improvements_text = "\n\n🔧 **التحسينات / Improvements:**\n" + \
                              "\n".join([f"  • {i}" for i in improvements])

        message = (
            "🎉 **تحديث جديد / New Update!**\n"
            "═══════════════════════════════\n\n"
            f"📦 **الإصدار / Version:** {version}\n\n"
            "✨ **المميزات الجديدة / New Features:**\n"
            f"{features_text}"
            f"{improvements_text}\n\n"
            f"🕒 **التاريخ / Date:** {timestamp}\n\n"
            "🚀 التحديث مفعّل الآن!"
        )

        return await self._send_message(bot, self.updates_channel, message, "Updates")

    async def announce_maintenance(
        self,
        bot: Bot,
        start_time: str,
        duration: str,
        reason: str = "صيانة دورية / Routine maintenance"
    ) -> bool:
        """
        Announce scheduled maintenance

        Args:
            bot: Telegram Bot instance
            start_time: Maintenance start time
            duration: Expected duration
            reason: Maintenance reason

        Returns:
            bool: True if successful
        """
        message = (
            "🔧 **صيانة مجدولة / Scheduled Maintenance**\n"
            "═══════════════════════════════\n\n"
            f"📅 **الوقت / Time:** {start_time}\n"
            f"⏱️ **المدة / Duration:** {duration}\n"
            f"📝 **السبب / Reason:** {reason}\n\n"
            "⚠️ البوت قد يكون غير متاح مؤقتاً\n"
            "⚠️ Bot may be temporarily unavailable"
        )

        return await self._send_message(bot, self.updates_channel, message, "Updates")


# Create global instance
channel_manager = ChannelManager()
