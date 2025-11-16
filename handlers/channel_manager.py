"""
Channel Manager System
نظام إدارة القنوات للبوت

This module manages all bot channels:
1. Logs Channel - For bot events and errors
2. Videos Channel - For downloaded videos backup
3. New Users Channel - For new user registrations
4. Statistics Channel - For daily statistics
5. Admin Channel - For automatic notifications (stop, start, maintenance)
6. Updates Channel - For manual announcements (@iraq_7kmmy - no automatic messages)
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
        self.admin_channel = os.getenv("ADMIN_CHANNEL_ID")
        self.updates_channel = os.getenv("UPDATES_CHANNEL_USERNAME", "@iraq_7kmmy")

        # Log which channels are configured
        self._log_configuration()

    def _log_configuration(self):
        """Log which channels are configured with detailed information"""
        logger.info("=" * 70)
        logger.info("📢 CHANNEL MANAGER CONFIGURATION")
        logger.info("=" * 70)

        # تحليل شامل لكل قناة
        channels_info = [
            {
                "name": "Logs Channel",
                "id": self.log_channel,
                "env_var": "LOG_CHANNEL_ID",
                "purpose": "Bot events and errors logging"
            },
            {
                "name": "Videos Channel",
                "id": self.videos_channel,
                "env_var": "VIDEOS_CHANNEL_ID",
                "purpose": "Downloaded videos backup"
            },
            {
                "name": "New Users Channel",
                "id": self.new_users_channel,
                "env_var": "NEW_USERS_CHANNEL_ID",
                "purpose": "New user registrations tracking"
            },
            {
                "name": "Statistics Channel",
                "id": self.stats_channel,
                "env_var": "STATS_CHANNEL_ID",
                "purpose": "Daily statistics reports"
            },
            {
                "name": "Admin Channel",
                "id": self.admin_channel,
                "env_var": "ADMIN_CHANNEL_ID",
                "purpose": "Automatic notifications (startup/shutdown)"
            },
            {
                "name": "Updates Channel",
                "id": self.updates_channel,
                "env_var": "UPDATES_CHANNEL_USERNAME",
                "purpose": "Manual announcements only (@iraq_7kmmy)"
            }
        ]

        configured_count = 0
        missing_count = 0

        for channel in channels_info:
            if channel["id"]:
                configured_count += 1
                logger.info(f"✅ {channel['name']}: CONFIGURED")
                logger.info(f"   └─ ID: {channel['id']}")
                logger.info(f"   └─ Purpose: {channel['purpose']}")
            else:
                missing_count += 1
                logger.warning(f"❌ {channel['name']}: NOT CONFIGURED")
                logger.warning(f"   └─ Env Variable: {channel['env_var']}")
                logger.warning(f"   └─ Purpose: {channel['purpose']}")
                logger.warning(f"   └─ Action Required: Add {channel['env_var']} to .env file")

            logger.info("-" * 70)

        # ملخص
        logger.info(f"📊 SUMMARY: {configured_count}/6 channels configured")

        if missing_count > 0:
            logger.warning(f"⚠️ WARNING: {missing_count} channel(s) not configured")
            logger.warning(f"💡 Some features may not work without these channels")
            logger.warning(f"📝 Add the missing environment variables to .env file")
        else:
            logger.info(f"🎉 All channels are configured correctly!")

        logger.info("=" * 70)

    def _get_timestamp(self) -> str:
        """Get formatted timestamp"""
        return datetime.now().strftime("%H:%M — %d-%m-%Y")

    async def test_all_channels(self, bot: Bot) -> dict:
        """
        Test connectivity to all configured channels
        This is useful for diagnosing channel setup issues

        Args:
            bot: Telegram Bot instance

        Returns:
            dict: Results of channel tests {channel_name: success_status}
        """
        logger.info("=" * 70)
        logger.info("🧪 TESTING CHANNEL CONNECTIVITY")
        logger.info("=" * 70)

        test_results = {}
        channels_to_test = [
            ("Logs", self.log_channel),
            ("Videos", self.videos_channel),
            ("New Users", self.new_users_channel),
            ("Statistics", self.stats_channel),
            ("Admin", self.admin_channel),
        ]

        for channel_name, channel_id in channels_to_test:
            if not channel_id:
                logger.warning(f"⏭️ Skipping {channel_name}: Not configured")
                test_results[channel_name] = "not_configured"
                continue

            logger.info(f"🔍 Testing {channel_name} channel ({channel_id})...")

            try:
                # محاولة الحصول على معلومات القناة
                chat = await bot.get_chat(chat_id=channel_id)

                # التحقق من أن البوت عضو في القناة
                bot_member = await bot.get_chat_member(
                    chat_id=channel_id,
                    user_id=bot.id
                )

                # التحقق من الصلاحيات
                can_post = bot_member.status in ["administrator", "creator"]
                can_edit = getattr(bot_member, "can_post_messages", False) if bot_member.status == "administrator" else True

                if can_post:
                    logger.info(f"   ✅ {channel_name}: Connection successful")
                    logger.info(f"      └─ Channel Title: {chat.title}")
                    logger.info(f"      └─ Bot Status: {bot_member.status}")
                    logger.info(f"      └─ Can Post: {'Yes' if can_edit or bot_member.status == 'creator' else 'No'}")
                    test_results[channel_name] = "success"
                else:
                    logger.error(f"   ❌ {channel_name}: Bot is not admin!")
                    logger.error(f"      └─ Bot Status: {bot_member.status}")
                    logger.error(f"      └─ Action: Make bot admin in the channel")
                    test_results[channel_name] = "not_admin"

            except TelegramError as e:
                error_str = str(e).lower()
                if "chat not found" in error_str:
                    logger.error(f"   ❌ {channel_name}: Channel not found")
                    logger.error(f"      └─ Channel ID: {channel_id}")
                    logger.error(f"      └─ Issue: Invalid channel ID or bot removed")
                    test_results[channel_name] = "not_found"
                elif "forbidden" in error_str:
                    logger.error(f"   ❌ {channel_name}: Access forbidden")
                    logger.error(f"      └─ Issue: Bot not added to channel or blocked")
                    test_results[channel_name] = "forbidden"
                else:
                    logger.error(f"   ❌ {channel_name}: Telegram error - {str(e)}")
                    test_results[channel_name] = f"error: {str(e)}"

            except Exception as e:
                logger.error(f"   ❌ {channel_name}: Unexpected error - {str(e)}")
                test_results[channel_name] = f"unexpected_error: {str(e)}"

        # ملخص النتائج
        logger.info("-" * 70)
        success_count = sum(1 for v in test_results.values() if v == "success")
        total_configured = sum(1 for v in test_results.values() if v != "not_configured")

        logger.info(f"📊 TEST RESULTS: {success_count}/{total_configured} channels accessible")

        if success_count == total_configured and total_configured > 0:
            logger.info(f"🎉 All configured channels are working correctly!")
        elif success_count > 0:
            logger.warning(f"⚠️ Some channels have issues - check logs above")
        else:
            logger.error(f"❌ No channels are accessible - check configuration")

        logger.info("=" * 70)

        return test_results

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
        Internal method to send message to a channel with detailed error tracking

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
        # تحقق من وجود معرف القناة
        if not channel_id:
            logger.warning(f"=" * 60)
            logger.warning(f"⚠️ CHANNEL ERROR: {channel_name} channel not configured!")
            logger.warning(f"📝 Channel Name: {channel_name}")
            logger.warning(f"🔴 Issue: No channel ID found in environment variables")
            logger.warning(f"💡 Solution:")

            # اقتراحات بناءً على اسم القناة
            env_var_map = {
                "Logs": "LOG_CHANNEL_ID",
                "Videos": "VIDEOS_CHANNEL_ID",
                "New Users": "NEW_USERS_CHANNEL_ID",
                "Statistics": "STATS_CHANNEL_ID",
                "Admin": "ADMIN_CHANNEL_ID",
                "Updates (Manual)": "UPDATES_CHANNEL_USERNAME"
            }

            env_var = env_var_map.get(channel_name, f"{channel_name.upper()}_CHANNEL_ID")
            logger.warning(f"   1. Add {env_var} to your .env file")
            logger.warning(f"   2. Make sure the bot is added as admin to the channel")
            logger.warning(f"   3. Restart the bot after adding the environment variable")
            logger.warning(f"=" * 60)
            return False

        # تسجيل تفاصيل محاولة الإرسال
        logger.info(f"━" * 60)
        logger.info(f"📤 ATTEMPTING TO SEND MESSAGE TO CHANNEL")
        logger.info(f"📝 Channel Name: {channel_name}")
        logger.info(f"🆔 Channel ID: {channel_id}")
        logger.info(f"📏 Message Length: {len(message)} characters")
        logger.info(f"🎨 Parse Mode: {parse_mode}")
        logger.info(f"🔕 Silent: {disable_notification}")
        logger.info(f"━" * 60)

        try:
            # محاولة الإرسال
            result = await bot.send_message(
                chat_id=channel_id,
                text=message,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )

            # تسجيل نجاح الإرسال
            logger.info(f"✅ SUCCESS: Message sent to {channel_name} channel")
            logger.info(f"📨 Message ID: {result.message_id}")
            logger.info(f"⏰ Sent at: {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"━" * 60)
            return True

        except TelegramError as e:
            # تتبع تفصيلي لأخطاء Telegram
            logger.error(f"=" * 60)
            logger.error(f"❌ TELEGRAM ERROR: Failed to send to {channel_name} channel")
            logger.error(f"📝 Channel Name: {channel_name}")
            logger.error(f"🆔 Channel ID: {channel_id}")
            logger.error(f"🔴 Error Type: {type(e).__name__}")
            logger.error(f"📄 Error Message: {str(e)}")

            # تحليل أنواع الأخطاء الشائعة
            error_str = str(e).lower()

            if "chat not found" in error_str or "chat_not_found" in error_str:
                logger.error(f"💡 DIAGNOSIS: Channel ID is invalid or bot cannot find the channel")
                logger.error(f"✅ SOLUTIONS:")
                logger.error(f"   1. Verify the channel ID is correct: {channel_id}")
                logger.error(f"   2. Make sure the channel exists and is not deleted")
                logger.error(f"   3. Check if the ID format is correct (should start with -100)")
                logger.error(f"   4. For usernames, ensure format is @channelname")

            elif "forbidden" in error_str or "bot was blocked" in error_str:
                logger.error(f"💡 DIAGNOSIS: Bot doesn't have permission to send messages")
                logger.error(f"✅ SOLUTIONS:")
                logger.error(f"   1. Add the bot as an administrator to the channel")
                logger.error(f"   2. Grant 'Post Messages' permission to the bot")
                logger.error(f"   3. If bot was removed, re-add it to the channel")
                logger.error(f"   4. Verify bot token is correct and active")

            elif "message is too long" in error_str:
                logger.error(f"💡 DIAGNOSIS: Message exceeds Telegram's 4096 character limit")
                logger.error(f"✅ SOLUTIONS:")
                logger.error(f"   1. Current message length: {len(message)} characters")
                logger.error(f"   2. Need to split message into multiple parts")
                logger.error(f"   3. Or reduce message content")

            elif "can't parse" in error_str or "parse_mode" in error_str:
                logger.error(f"💡 DIAGNOSIS: Invalid Markdown/HTML formatting in message")
                logger.error(f"✅ SOLUTIONS:")
                logger.error(f"   1. Check for unescaped special characters")
                logger.error(f"   2. Verify Markdown syntax is correct")
                logger.error(f"   3. Try sending without parse_mode to test")
                logger.error(f"📝 Message preview (first 200 chars):")
                logger.error(f"   {message[:200]}")

            elif "timeout" in error_str or "timed out" in error_str:
                logger.error(f"💡 DIAGNOSIS: Network timeout - connection to Telegram servers failed")
                logger.error(f"✅ SOLUTIONS:")
                logger.error(f"   1. Check internet connection")
                logger.error(f"   2. Retry the operation")
                logger.error(f"   3. Check if Telegram API is down")

            else:
                logger.error(f"💡 DIAGNOSIS: Unknown Telegram error")
                logger.error(f"✅ SOLUTIONS:")
                logger.error(f"   1. Check Telegram API documentation for error code")
                logger.error(f"   2. Verify bot token and permissions")
                logger.error(f"   3. Contact Telegram support if issue persists")
                logger.error(f"📝 Full error details: {repr(e)}")

            logger.error(f"=" * 60)
            return False

        except Exception as e:
            # تتبع تفصيلي للأخطاء العامة
            logger.error(f"=" * 60)
            logger.error(f"❌ UNEXPECTED ERROR: Failed to send to {channel_name} channel")
            logger.error(f"📝 Channel Name: {channel_name}")
            logger.error(f"🆔 Channel ID: {channel_id}")
            logger.error(f"🔴 Error Type: {type(e).__name__}")
            logger.error(f"📄 Error Message: {str(e)}")
            logger.error(f"📍 Error Details: {repr(e)}")

            # استخراج stack trace إذا كان متاحاً
            import traceback
            stack_trace = traceback.format_exc()
            logger.error(f"📚 Stack Trace:")
            logger.error(stack_trace)

            logger.error(f"💡 DIAGNOSIS: Unexpected error - not a Telegram API error")
            logger.error(f"✅ SOLUTIONS:")
            logger.error(f"   1. Check the error stack trace above")
            logger.error(f"   2. Verify bot object is properly initialized")
            logger.error(f"   3. Check for coding errors in the message content")
            logger.error(f"   4. Report this error if it persists")
            logger.error(f"=" * 60)
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
        Log error to logs channel with Design #3 (professional with details)

        Args:
            bot: Telegram Bot instance
            error_type: Type of error
            error_message: Error message
            user_id: Optional user ID who triggered the error

        Returns:
            bool: True if successful
        """
        import re

        timestamp = self._get_timestamp()

        # 1. إزالة رموز الألوان ANSI
        # Remove ANSI color codes like [0;31m, [0m, etc.
        clean_error = re.sub(r'\x1b\[[0-9;]*m', '', error_message)
        clean_error = re.sub(r'\[0;[0-9]+m', '', clean_error)
        clean_error = re.sub(r'\[0m', '', clean_error)

        # 2. اختصار الروابط الطويلة
        # Shorten long URLs (keep first 60 chars + ... + last 20 chars)
        def shorten_url(match):
            url = match.group(0)
            if len(url) > 100:
                return url[:60] + "..." + url[-20:]
            return url

        url_pattern = r'https?://[^\s]+'
        clean_error = re.sub(url_pattern, shorten_url, clean_error)

        # 3. اختصار الرسالة إذا كانت طويلة جداً
        if len(clean_error) > 400:
            clean_error = clean_error[:400] + "..."

        # 4. إنشاء رابط المستخدم القابل للنقر (مثل تنبيهات الأعضاء الجدد)
        user_info = ""
        if user_id:
            user_link = f"tg://user?id={user_id}"
            user_info = f"\n👤 **المستخدم:** [ID: {user_id}]({user_link})"

        # 5. التصميم رقم 3 - احترافي مع التفاصيل
        message = (
            "⚠️ **تنبيه خطأ**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔴 **نوع الخطأ:**\n{error_type}\n\n"
            f"📋 **التفاصيل:**\n```\n{clean_error}\n```"
            f"{user_info}\n\n"
            f"🕐 **الوقت:** {timestamp.split(' — ')[0]}\n"
            f"📅 **التاريخ:** {timestamp.split(' — ')[1]}"
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
        Enhanced with beautiful Design #6 and direct message link

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

        # تنسيق اللغة
        lang_map = {
            'ar': 'العربية 🇸🇦',
            'en': 'English 🇬🇧',
            'es': 'Español 🇪🇸',
            'fr': 'Français 🇫🇷',
            'de': 'Deutsch 🇩🇪',
            'ru': 'Русский 🇷🇺'
        }
        lang_display = lang_map.get(language_code, language_code or "Unknown")

        # إنشاء رابط المراسلة المباشرة (يعمل حتى بدون يوزر)
        user_link = f"tg://user?id={user_id}"

        # تنسيق اليوزر
        if username:
            username_display = f"@{username}"
        else:
            username_display = "لا يوجد"

        # معلومات الإحالة
        referral_info = ""
        if referrer_id:
            referral_info = f"\n🔗 **المُحيل:** `{referrer_id}`"

        # محاولة جلب إجمالي الأعضاء
        try:
            from database import get_all_users
            total_users = len(get_all_users())
            stats_info = f"\n\n━━━━━━━━━━━━━━━━━━━━━\n\n📊 **إحصائيات:**\n💎 إجمالي الأعضاء: **{total_users:,}**"
        except Exception:
            stats_info = ""

        # التصميم رقم 6 المحسّن مع رابط المراسلة
        message = (
            "🎊 **عضو جديد انضم للبوت!**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**المعلومات الشخصية:**\n"
            f"👤 **الاسم:** [{first_name}]({user_link})\n"
            f"🔗 **اليوزر:** {username_display}\n"
            f"🆔 **الآيدي:** `{user_id}`\n"
            f"🌐 **اللغة:** {lang_display}"
            f"{referral_info}\n\n"
            "**تفاصيل الانضمام:**\n"
            f"📅 **التاريخ:** {timestamp.split(' — ')[1]}\n"
            f"🕐 **الوقت:** {timestamp.split(' — ')[0]}"
            f"{stats_info}"
        )

        return await self._send_message(
            bot,
            self.new_users_channel,
            message,
            "New Users",
            parse_mode='Markdown',
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
    # ADMIN CHANNEL METHODS
    # القناة الإدارية - للإشعارات التلقائية فقط
    # ═══════════════════════════════════════════════════════════

    async def notify_bot_startup(self, bot: Bot) -> bool:
        """
        Send bot startup notification to admin channel

        Args:
            bot: Telegram Bot instance

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()
        message = (
            "🚀 **تشغيل البوت / Bot Started**\n\n"
            "✅ **جميع الأنظمة تعمل / All Systems Operational**\n\n"
            "🎯 **المميزات النشطة / Active Features:**\n"
            "• تحميل فيديوهات من +1000 موقع\n"
            "• نظام اختيار فيديوهات محددة من القوائم\n"
            "• تتبع دقيق للتقدم (1%)\n"
            "• تفاعلات تلقائية 👀\n"
            "• نظام الإحالة والمكافآت\n"
            "• نظام قنوات متعددة 📢\n\n"
            f"🕒 **الوقت / Time:** {timestamp}\n"
            "⚡ **الحالة / Status:** جاهز للاستخدام"
        )
        return await self._send_message(bot, self.admin_channel, message, "Admin")

    async def notify_bot_shutdown(self, bot: Bot, reason: str = "Normal shutdown") -> bool:
        """
        Send bot shutdown notification to admin channel

        Args:
            bot: Telegram Bot instance
            reason: Shutdown reason

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()
        message = (
            "⏹️ **توقف البوت / Bot Stopped**\n\n"
            f"📝 **السبب / Reason:** {reason}\n"
            f"🕒 **الوقت / Time:** {timestamp}\n\n"
            "🔄 سيتم إعادة التشغيل قريباً..."
        )
        return await self._send_message(bot, self.admin_channel, message, "Admin")

    async def notify_critical_error(
        self,
        bot: Bot,
        error_type: str,
        error_message: str
    ) -> bool:
        """
        Send critical error notification to admin channel

        Args:
            bot: Telegram Bot instance
            error_type: Type of error
            error_message: Error message

        Returns:
            bool: True if successful
        """
        timestamp = self._get_timestamp()

        # Truncate long error messages
        if len(error_message) > 300:
            error_message = error_message[:300] + "..."

        message = (
            "🚨 **خطأ حرج / Critical Error**\n\n"
            f"🔴 **النوع / Type:** {error_type}\n"
            f"📝 **التفاصيل / Details:**\n`{error_message}`\n\n"
            f"🕒 **الوقت / Time:** {timestamp}\n"
            "⚠️ **يتطلب انتباهك / Requires Attention**"
        )
        return await self._send_message(bot, self.admin_channel, message, "Admin")

    async def notify_maintenance(
        self,
        bot: Bot,
        start_time: str,
        duration: str,
        reason: str = "صيانة دورية / Routine maintenance"
    ) -> bool:
        """
        Send maintenance notification to admin channel

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
            "⚠️ البوت قد يكون غير متاح مؤقتاً"
        )
        return await self._send_message(bot, self.admin_channel, message, "Admin")

    # ═══════════════════════════════════════════════════════════
    # UPDATES CHANNEL METHODS
    # قناة التحديثات - للإعلانات اليدوية فقط (لا رسائل تلقائية)
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
        NOTE: This is for MANUAL announcements only
        The bot will NOT automatically send to @iraq_7kmmy
        Use this only when you want to manually announce something

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

        # This will NOT be called automatically
        # Only use when you manually want to announce
        logger.warning("⚠️ announce_update called - This sends to public @iraq_7kmmy channel!")
        return await self._send_message(bot, self.updates_channel, message, "Updates (Manual)")

    async def announce_maintenance_public(
        self,
        bot: Bot,
        start_time: str,
        duration: str,
        reason: str = "صيانة دورية / Routine maintenance"
    ) -> bool:
        """
        Announce scheduled maintenance to PUBLIC updates channel
        NOTE: This is for MANUAL announcements only

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

        logger.warning("⚠️ announce_maintenance_public called - This sends to public @iraq_7kmmy channel!")
        return await self._send_message(bot, self.updates_channel, message, "Updates (Manual)")


# Create global instance
channel_manager = ChannelManager()
