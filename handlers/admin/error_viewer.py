"""
عارض الأخطاء للمدير
Admin Error Viewer

يسمح للمدير باستعراض الأخطاء المسجلة في النظام
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.utils.error_tracker import ErrorTracker
from database import is_admin
import json

logger = logging.getLogger(__name__)


async def cmd_errors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    أمر /errors - عرض الأخطاء الأخيرة (للمدير فقط)
    """
    user_id = update.effective_user.id

    # التحقق من صلاحيات المدير
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمدراء فقط!")
        return

    # الحصول على الإحصائيات
    stats = ErrorTracker.get_error_stats(hours=24)

    if stats['total'] == 0:
        await update.message.reply_text(
            "✅ **لا توجد أخطاء في آخر 24 ساعة!**\n\n"
            "البوت يعمل بشكل ممتاز 🎉",
            parse_mode='Markdown'
        )
        return

    # تنسيق الإحصائيات
    report = (
        f"📊 **تقرير الأخطاء - آخر 24 ساعة**\n\n"
        f"📈 **إجمالي الأخطاء:** {stats['total']}\n\n"
    )

    # الأخطاء حسب النوع
    if stats['by_type']:
        report += "🔹 **حسب النوع:**\n"
        for error_type, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True):
            report += f"• `{error_type}`: {count}\n"
        report += "\n"

    # الأخطاء حسب الفئة
    if stats['by_category']:
        report += "🔸 **حسب الفئة:**\n"
        for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
            report += f"• `{category}`: {count}\n"
        report += "\n"

    # الأخطاء حسب المنصة
    if stats['by_platform']:
        report += "🌐 **حسب المنصة:**\n"
        for platform, count in sorted(stats['by_platform'].items(), key=lambda x: x[1], reverse=True):
            if platform != "unknown":
                report += f"• `{platform}`: {count}\n"

    # أزرار للتفاصيل
    keyboard = [
        [
            InlineKeyboardButton("📝 آخر 10 أخطاء", callback_data="errors_recent_10"),
            InlineKeyboardButton("📋 آخر 20", callback_data="errors_recent_20")
        ],
        [
            InlineKeyboardButton("🔴 Facebook فقط", callback_data="errors_facebook"),
            InlineKeyboardButton("📸 Instagram فقط", callback_data="errors_instagram")
        ],
        [InlineKeyboardButton("🔄 تحديث", callback_data="errors_refresh")]
    ]

    await update.message.reply_text(
        report,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_errors_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أزرار عرض الأخطاء"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.answer("⛔ للمدراء فقط!", show_alert=True)
        return

    data = query.data

    if data == "errors_refresh":
        # تحديث الإحصائيات
        stats = ErrorTracker.get_error_stats(hours=24)

        if stats['total'] == 0:
            await query.edit_message_text(
                "✅ **لا توجد أخطاء في آخر 24 ساعة!**\n\n"
                "البوت يعمل بشكل ممتاز 🎉",
                parse_mode='Markdown'
            )
            return

        # تنسيق الإحصائيات
        report = (
            f"📊 **تقرير الأخطاء - آخر 24 ساعة**\n\n"
            f"📈 **إجمالي الأخطاء:** {stats['total']}\n\n"
        )

        if stats['by_type']:
            report += "🔹 **حسب النوع:**\n"
            for error_type, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True):
                report += f"• `{error_type}`: {count}\n"
            report += "\n"

        if stats['by_category']:
            report += "🔸 **حسب الفئة:**\n"
            for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
                report += f"• `{category}`: {count}\n"
            report += "\n"

        if stats['by_platform']:
            report += "🌐 **حسب المنصة:**\n"
            for platform, count in sorted(stats['by_platform'].items(), key=lambda x: x[1], reverse=True):
                if platform != "unknown":
                    report += f"• `{platform}`: {count}\n"

        keyboard = [
            [
                InlineKeyboardButton("📝 آخر 10 أخطاء", callback_data="errors_recent_10"),
                InlineKeyboardButton("📋 آخر 20", callback_data="errors_recent_20")
            ],
            [
                InlineKeyboardButton("🔴 Facebook فقط", callback_data="errors_facebook"),
                InlineKeyboardButton("📸 Instagram فقط", callback_data="errors_instagram")
            ],
            [InlineKeyboardButton("🔄 تحديث", callback_data="errors_refresh")]
        ]

        await query.edit_message_text(
            report,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("errors_recent_"):
        # عرض الأخطاء الأخيرة
        limit = int(data.split("_")[-1])
        errors = ErrorTracker.get_recent_errors(limit=limit)

        if not errors:
            await query.edit_message_text("✅ لا توجد أخطاء!", parse_mode='Markdown')
            return

        report = f"📝 **آخر {len(errors)} خطأ:**\n\n"

        for i, error in enumerate(reversed(errors), 1):
            timestamp = error.get('timestamp', 'N/A')[:19]  # YYYY-MM-DD HH:MM:SS
            error_type = error.get('error_type', 'unknown')
            platform = error.get('context', {}).get('platform', 'unknown')
            category = error.get('context', {}).get('error_category', 'unknown')

            report += (
                f"**{i}.** `{error_type}`\n"
                f"   ⏰ {timestamp}\n"
                f"   🌐 {platform} | 🔖 {category}\n\n"
            )

            # حد أقصى للطول
            if len(report) > 3500:
                report += "\n_... والمزيد_"
                break

        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="errors_refresh")]]

        await query.edit_message_text(
            report,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("errors_"):
        # تصفية حسب المنصة
        platform = data.replace("errors_", "")
        errors = ErrorTracker.get_recent_errors(limit=20)

        # تصفية الأخطاء للمنصة المطلوبة
        platform_errors = [
            e for e in errors
            if e.get('context', {}).get('platform', '') == platform
        ]

        if not platform_errors:
            await query.edit_message_text(
                f"✅ لا توجد أخطاء لـ {platform} في آخر 20 خطأ!",
                parse_mode='Markdown'
            )
            return

        report = f"🔍 **أخطاء {platform.title()}:**\n\n"

        for i, error in enumerate(reversed(platform_errors), 1):
            timestamp = error.get('timestamp', 'N/A')[:19]
            category = error.get('context', {}).get('error_category', 'unknown')
            error_msg = error.get('error_message', 'N/A')

            # اختصار رسالة الخطأ
            if len(error_msg) > 80:
                error_msg = error_msg[:80] + "..."

            report += (
                f"**{i}.** `{category}`\n"
                f"   ⏰ {timestamp}\n"
                f"   ❌ {error_msg}\n\n"
            )

            if len(report) > 3500:
                report += "\n_... والمزيد_"
                break

        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="errors_refresh")]]

        await query.edit_message_text(
            report,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
