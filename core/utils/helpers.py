#!/usr/bin/env python3
"""
دوال مساعدة عامة
General helper utilities
"""

import os
import json
import threading
from time import time
from datetime import datetime
from functools import wraps, lru_cache
from telegram import BotCommand, BotCommandScopeChat

from config.logger import get_logger

logger = get_logger(__name__)

# تهيئة الرسائل والإعدادات كمتغيرات عامة
MESSAGES = {}
CONFIG = {}

# ==================== تحميل الإعدادات والرسائل ====================

def load_messages():
    """تحميل الرسائل من ملف messages.json"""
    global MESSAGES
    try:
        with open('messages.json', 'r', encoding='utf-8') as f:
            MESSAGES = json.load(f)
    except Exception as e:
        logger.error(f"❌ فشل تحميل الرسائل: {e}")
        MESSAGES = {}


def load_config():
    """يقوم بتحميل الإعدادات من ملف JSON ودمجها مع متغيرات البيئة"""
    global CONFIG
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            CONFIG = json.load(f)
        logger.info("✅ تم تحميل ملف الإعدادات بنجاح.")

        # ⭐ دمج المتغيرات السرية من ملف .env
        # إضافة بيانات Binance من متغيرات البيئة
        CONFIG['binance_api_key'] = os.getenv('BINANCE_API_KEY', 'YOUR_BINANCE_API_KEY_HERE')
        CONFIG['binance_secret_key'] = os.getenv('BINANCE_SECRET_KEY', 'YOUR_BINANCE_SECRET_KEY_HERE')

        # إضافة معلومات الدفع عبر Instagram من متغيرات البيئة
        CONFIG['instagram_payment'] = {
            'username': os.getenv('INSTAGRAM_PAYMENT_USERNAME', '7kmmy'),
            'message_ar': f"شكراً لاختيارك! تواصل عبر الإنستغرام @{os.getenv('INSTAGRAM_PAYMENT_USERNAME', '7kmmy')} للدفع",
            'message_en': f"Thank you for choosing! Contact @{os.getenv('INSTAGRAM_PAYMENT_USERNAME', '7kmmy')} on Instagram for payment"
        }

        # إضافة سعر الاشتراك من متغيرات البيئة
        CONFIG['subscription_price_usd'] = float(os.getenv('SUBSCRIPTION_PRICE_USD', '3.0'))

        logger.info("✅ تم دمج متغيرات البيئة مع الإعدادات.")

    except FileNotFoundError:
        logger.error("!!! ملف config.json غير موجود. سيتم استخدام إعدادات افتراضية.")
        CONFIG = {}
    except json.JSONDecodeError:
        logger.error("!!! خطأ في قراءة ملف config.json. تأكد من أن تنسيقه صحيح.")
        CONFIG = {}


def get_message(lang, key):
    """الحصول على رسالة محددة"""
    return MESSAGES.get(lang, {}).get(key, key)


def get_config():
    """يجلب الإعدادات المحملة"""
    return CONFIG


# ==================== إعداد قائمة أوامر البوت ====================

async def setup_bot_menu(bot):
    """يقوم بإعداد قائمة الأوامر (Menu) للبوت"""
    logger.info("📋 إعداد قائمة أوامر البوت...")

    if not MESSAGES:
        load_messages()

    user_commands_ar = [
        BotCommand("start", get_message('ar', 'start_command_desc')),
        BotCommand("account", get_message('ar', 'account_command_desc')),
        BotCommand("help", get_message('ar', 'help_command_desc')),
    ]

    user_commands_en = [
        BotCommand("start", get_message('en', 'start_command_desc')),
        BotCommand("account", get_message('en', 'account_command_desc')),
        BotCommand("help", get_message('en', 'help_command_desc')),
    ]

    admin_commands_ar = user_commands_ar + [
        BotCommand("admin", get_message('ar', 'admin_command_desc')),
    ]

    admin_commands_en = user_commands_en + [
        BotCommand("admin", get_message('en', 'admin_command_desc')),
    ]

    await bot.set_my_commands(user_commands_ar)
    logger.info("✅ تم تعيين قائمة الأوامر العامة.")

    # Parse ADMIN_IDs safely
    admin_ids_str = os.getenv("ADMIN_ID", "")
    try:
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip().isdigit()]
    except (ValueError, AttributeError) as e:
        logger.error(f"❌ Failed to parse ADMIN_ID: {e}")
        admin_ids = []

    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(admin_commands_ar, scope=BotCommandScopeChat(chat_id=admin_id))
            logger.info(f"✅ تم تعيين قائمة أوامر خاصة للمدير ID: {admin_id}")
        except Exception as e:
            logger.error(f"❌ فشل تعيين أوامر للمدير {admin_id}: {e}")


# ==================== تحديد معدل الطلبات (Rate Limiting) ====================

# قاموس لتتبع آخر طلب لكل مستخدم
_user_last_request = {}
# Performance optimization: reduced from 10 to 3 seconds for faster response
_RATE_LIMIT_SECONDS = 3  # 3 ثواني بين كل طلب


def rate_limit(seconds: int = None):
    """
    ديكوراتور لتحديد معدل الطلبات - يمنع المستخدم من إرسال طلبات متكررة

    Args:
        seconds: عدد الثواني المطلوبة بين كل طلب (افتراضي: 10 ثواني)

    Usage:
        @rate_limit(seconds=10)
        async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # download code here
    """
    limit = seconds if seconds is not None else _RATE_LIMIT_SECONDS

    def decorator(func):
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            current_time = time()

            # التحقق من آخر طلب للمستخدم
            last_request = _user_last_request.get(user_id, 0)
            time_passed = current_time - last_request

            if time_passed < limit:
                remaining = int(limit - time_passed)

                # الحصول على لغة المستخدم
                user_lang = 'ar'
                try:
                    from database import get_user_language
                    user_lang = get_user_language(user_id)
                except:
                    pass

                if user_lang == 'ar':
                    error_msg = f"⏱️ الرجاء الانتظار {remaining} ثانية قبل إرسال طلب جديد."
                else:
                    error_msg = f"⏱️ Please wait {remaining} seconds before sending a new request."

                await update.message.reply_text(error_msg)
                return None

            # تحديث وقت آخر طلب
            _user_last_request[user_id] = current_time

            # تنفيذ الأمر
            return await func(update, context, *args, **kwargs)

        return wrapper
    return decorator


# ==================== تخزين مؤقت لبيانات المستخدم ====================

# Cache لبيانات المستخدم (يتم تحديثه كل 60 ثانية)
_user_cache = {}
_user_cache_ttl = 60  # ثانية
_cache_lock = threading.Lock()


def get_cached_user_data(user_id: int, fetch_func):
    """
    الحصول على بيانات المستخدم من الذاكرة المؤقتة أو جلبها من قاعدة البيانات

    Args:
        user_id: معرف المستخدم
        fetch_func: دالة لجلب البيانات من قاعدة البيانات

    Returns:
        بيانات المستخدم
    """
    current_time = time()

    with _cache_lock:
        # التحقق من وجود البيانات في الذاكرة المؤقتة
        if user_id in _user_cache:
            cached_data, timestamp = _user_cache[user_id]

            # إذا كانت البيانات لا تزال صالحة
            if current_time - timestamp < _user_cache_ttl:
                return cached_data

        # جلب البيانات من قاعدة البيانات
        user_data = fetch_func(user_id)

        # تخزين في الذاكرة المؤقتة
        _user_cache[user_id] = (user_data, current_time)

        return user_data


def clear_user_cache(user_id: int = None):
    """
    مسح الذاكرة المؤقتة لمستخدم معين أو جميع المستخدمين

    Args:
        user_id: معرف المستخدم (اختياري - إذا لم يُحدد، سيتم مسح الجميع)
    """
    with _cache_lock:
        if user_id:
            _user_cache.pop(user_id, None)
        else:
            _user_cache.clear()


# ==================== حماية الأوامر الإدارية ====================

def admin_only(func):
    """
    ديكوراتور للتحقق من صلاحيات الإدارة قبل تنفيذ الأوامر الإدارية

    Usage:
        @admin_only
        async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # admin code here
    """
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        # الحصول على معرف المستخدم
        user_id = update.effective_user.id

        # التحقق من صلاحيات الإدارة
        from database import is_admin

        if not is_admin(user_id):
            # رسالة رفض الوصول
            user_lang = 'ar'  # افتراضياً العربية
            try:
                from database import get_user_language
                user_lang = get_user_language(user_id)
            except:
                pass

            if user_lang == 'ar':
                error_msg = "⛔ عذراً، هذا الأمر متاح للمشرفين فقط."
            else:
                error_msg = "⛔ Sorry, this command is only available for administrators."

            await update.message.reply_text(error_msg)

            # سجل محاولة الوصول غير المصرح بها
            username = update.effective_user.username or update.effective_user.first_name
            logger.warning(f"⚠️ محاولة وصول غير مصرح: المستخدم {username} ({user_id}) حاول تنفيذ {func.__name__}")

            return None

        # تنفيذ الأمر إذا كان المستخدم admin
        return await func(update, context, *args, **kwargs)

    return wrapper


# ==================== نظام السجلات الاحترافي ====================

# عداد الأخطاء في الذاكرة
_error_counter = {
    'critical': 0,
    'warning': 0,
    'last_reset': datetime.now()
}
_error_lock = threading.Lock()


def _increment_error_count(error_type: str):
    """زيادة عداد الأخطاء بشكل آمن"""
    with _error_lock:
        _error_counter[error_type] = _error_counter.get(error_type, 0) + 1


def get_error_stats() -> dict:
    """الحصول على إحصائيات الأخطاء"""
    with _error_lock:
        return _error_counter.copy()


def reset_error_stats():
    """إعادة تعيين إحصائيات الأخطاء"""
    with _error_lock:
        _error_counter['critical'] = 0
        _error_counter['warning'] = 0
        _error_counter['last_reset'] = datetime.now()


def _write_to_error_log(level: str, message: str, module: str):
    """كتابة الخطأ إلى ملف السجل المحلي"""
    try:
        log_file = 'bot_errors.log'
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] [{module}] {message}\n"

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Failed to write to error log: {e}")


def log_warning(message: str, module: str = "unknown"):
    """
    تسجيل تحذير محلي بدون إرسال إلى تيليجرام

    Args:
        message: رسالة التحذير
        module: اسم الوحدة/الملف
    """
    # تسجيل في السجل المحلي
    logger.warning(f"[{module}] {message}")

    # كتابة إلى ملف السجل
    _write_to_error_log("WARNING", message, module)

    # زيادة العداد
    _increment_error_count('warning')


def _send_telegram_message(chat_id: str, text: str, parse_mode: str = "Markdown"):
    """إرسال رسالة إلى تيليجرام باستخدام requests"""
    import requests

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token or not chat_id:
        return False

    try:
        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        response = requests.post(
            api_url,
            data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": False
            },
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ فشل إرسال رسالة تيليجرام: {e}")
        return False


def _send_telegram_video(chat_id: str, video_path: str, caption: str):
    """إرسال فيديو إلى تيليجرام مع تعليق"""
    import requests

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token or not chat_id or not video_path:
        return False

    try:
        api_url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
        # لا نستخدم parse_mode لتجنب مشاكل parsing مع الرموز الخاصة في عنوان الفيديو
        data = {
            "chat_id": chat_id,
            "caption": caption
        }

        # إذا كان الفيديو رابط URL
        if video_path.startswith("http"):
            data["video"] = video_path
            response = requests.post(api_url, data=data, timeout=20)
        else:
            # إذا كان الفيديو ملف محلي
            if not os.path.exists(video_path):
                logger.error(f"❌ ملف الفيديو غير موجود: {video_path}")
                return False

            with open(video_path, "rb") as video_file:
                files = {"video": video_file}
                response = requests.post(api_url, data=data, files=files, timeout=30)

        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ فشل إرسال فيديو تيليجرام: {e}")
        return False


def send_critical_log(message: str, module: str = "غير محدد"):
    """
    إرسال خطأ جسيم إلى قناة السجلات + إشعار الأدمن بتنسيق احترافي.
    استخدم هذه الدالة فقط للأخطاء الحرجة (فشل قاعدة البيانات، أعطال النظام، إلخ)

    Args:
        message: رسالة الخطأ
        module: اسم الوحدة/الملف الذي حدث فيه الخطأ

    Returns:
        bool: True إذا تم الإرسال بنجاح
    """
    # كتابة إلى ملف السجل المحلي
    _write_to_error_log("CRITICAL", message, module)

    # زيادة عداد الأخطاء الحرجة
    _increment_error_count('critical')

    log_channel_id = os.getenv("LOG_CHANNEL_ID")
    if not log_channel_id:
        logger.warning("⚠️ LOG_CHANNEL_ID غير محدد، لن يتم إرسال السجلات")
        return False

    # تنسيق الوقت بشكل جميل
    timestamp = datetime.utcnow().strftime("%H:%M — %d-%m-%Y")

    # بناء الرسالة بتنسيق احترافي محسّن
    text = (
        "🔥 *خطأ جسيم في النظام*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📁 *الوحدة:* `{module}`\n"
        f"🧩 *السبب:* خطأ غير متوقع\n"
        f"💬 *التفاصيل:* {message}\n"
        f"🕒 *الوقت:* {timestamp}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🚨 *تم إشعار الأدمن تلقائياً.*"
    )

    # إرسال إلى قناة السجلات
    success = _send_telegram_message(log_channel_id, text)

    # إشعار الأدمن
    admin_id = os.getenv("ADMIN_ID", "").split(',')[0].strip()
    if admin_id:
        admin_text = f"🚨 *تنبيه إداري عاجل:*\n\n{text}"
        _send_telegram_message(admin_id, admin_text)

    return success


def send_video_report(user_id: int, username: str, url: str, title: str,
                     size: str = "", video_path: str = None):
    """
    إرسال تقرير تحميل فيديو جديد إلى قناة الفيديوهات مع الفيديو نفسه بتنسيق احترافي.

    Args:
        user_id: معرف المستخدم في تيليجرام
        username: اسم المستخدم
        url: رابط الفيديو الأصلي
        title: عنوان الفيديو
        size: حجم الفيديو (اختياري)
        video_path: مسار الفيديو المحلي أو رابط URL (اختياري)

    Returns:
        bool: True إذا تم الإرسال بنجاح
    """
    log_channel_videos = os.getenv("LOG_CHANNEL_ID_VIDEOS")
    if not log_channel_videos:
        logger.warning("⚠️ LOG_CHANNEL_ID_VIDEOS غير محدد، لن يتم إرسال التقارير")
        return False

    # تنسيق الوقت
    timestamp = datetime.utcnow().strftime("%H:%M — %d-%m-%Y")

    # معالجة اسم المستخدم
    username_display = f"@{username}" if username else "بدون اسم مستخدم"

    # معالجة العنوان لتجنب مشاكل Markdown
    title_escaped = title.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

    # بناء الرسالة
    text = (
        "🎬 *تقرير تحميل فيديو جديد*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 *المستخدم:* {username_display} (`{user_id}`)\n"
        f"🔗 *الرابط:* [اضغط هنا لفتح الفيديو]({url})\n"
        f"🏷️ *العنوان:* {title_escaped}\n"
    )

    if size:
        text += f"📦 *الحجم:* {size}\n"

    text += f"🕒 *الوقت:* {timestamp}\n"
    text += "━━━━━━━━━━━━━━━━━━"

    # إرسال الفيديو مع التقرير أو التقرير فقط
    if video_path:
        text += "\n🎥 *الفيديو مرفق أدناه مباشرة*"
        success = _send_telegram_video(log_channel_videos, video_path, text)
    else:
        success = _send_telegram_message(log_channel_videos, text)

    return success


# ═══════════════════════════════════════════════════════════════
#  Daily Download Reports
# ═══════════════════════════════════════════════════════════════

async def send_daily_report(context):
    """
    إرسال تقرير يومي بإحصائيات التحميلات إلى LOG_CHANNEL_ID
    يتم استدعاؤها تلقائياً عبر job queue
    """
    from database import generate_daily_report

    log_channel_id = os.getenv("LOG_CHANNEL_ID")
    if not log_channel_id:
        logger.warning("⚠️ LOG_CHANNEL_ID غير محدد، لن يتم إرسال التقرير اليومي")
        return

    # توليد التقرير
    report = generate_daily_report()

    # إرسال التقرير
    try:
        await context.bot.send_message(
            chat_id=log_channel_id,
            text=report,
            parse_mode='Markdown'
        )
        logger.info("✅ تم إرسال التقرير اليومي بنجاح")
    except Exception as e:
        logger.error(f"❌ فشل إرسال التقرير اليومي: {e}")


def setup_daily_report_job(application):
    """
    إعداد مهمة إرسال التقرير اليومي
    يتم استدعاؤها من bot.py عند بدء التشغيل

    Args:
        application: كائن Application من python-telegram-bot
    """
    from datetime import time

    # إرسال التقرير يومياً في الساعة 23:59 بتوقيت UTC
    job_queue = application.job_queue

    if job_queue:
        job_queue.run_daily(
            send_daily_report,
            time=time(hour=23, minute=59, second=0),
            name='daily_download_report'
        )
        logger.info("✅ تم جدولة التقرير اليومي للساعة 23:59 UTC")
    else:
        logger.warning("⚠️ job_queue غير متاح، لن يتم جدولة التقرير اليومي")


# ═══════════════════════════════════════════════════════════════
#  Enhanced Error Logging
# ═══════════════════════════════════════════════════════════════

def log_error_to_file(error_type: str, user_id: int, url: str, exception: Exception):
    """
    تسجيل الأخطاء إلى ملف logs/errors.log

    Args:
        error_type: نوع الخطأ (download/upload/compression/etc)
        user_id: معرف المستخدم
        url: رابط الفيديو/الصوت
        exception: الاستثناء المرفوع
    """
    import traceback

    try:
        # إنشاء مجلد logs إذا لم يكن موجوداً
        os.makedirs('logs', exist_ok=True)

        # تنسيق الوقت
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # الحصول على traceback مختصر (آخر 3 أسطر فقط)
        tb_lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
        short_traceback = ''.join(tb_lines[-3:])

        # بناء رسالة السجل
        log_entry = (
            f"\n{'='*60}\n"
            f"[{timestamp}] {error_type.upper()} ERROR\n"
            f"User ID: {user_id}\n"
            f"URL: {url}\n"
            f"Exception: {type(exception).__name__}: {str(exception)}\n"
            f"Traceback:\n{short_traceback}"
            f"{'='*60}\n"
        )

        # كتابة إلى الملف
        with open('logs/errors.log', 'a', encoding='utf-8') as f:
            f.write(log_entry)

        logger.info(f"✅ Error logged to logs/errors.log: {error_type}")

    except Exception as e:
        logger.error(f"❌ Failed to write error log: {e}")


# ═══════════════════════════════════════════════════════════════
#  Cookie Management - Daily Check Job (Updated from Weekly)
# ═══════════════════════════════════════════════════════════════

async def check_cookies_daily(context):
    """
    مهمة فحص الـ cookies يومياً (محدثة من الفحص الأسبوعي)
    يتم استدعاؤها تلقائياً كل يوم

    Features:
    - فحص صلاحية cookies لجميع المنصات
    - اختبار كل منصة على حدة
    - إرسال تنبيهات مفصلة للأدمن عند الفشل
    - تتبع أعمار الكوكيز
    """
    try:
        from handlers.cookie_manager import cookie_manager
        from datetime import datetime

        logger.info("🍪 بدء الفحص اليومي للـ cookies...")

        # Get admin IDs from environment
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

        if not admin_ids:
            logger.warning("⚠️ لا توجد معرفات أدمن، لن يتم إرسال التنبيهات")
            return

        # Get all cookie statuses
        status = cookie_manager.get_cookie_status()

        # ⭐ قائمة المنصات المدعومة (متضمنة Threads)
        platforms_to_check = ['facebook', 'instagram', 'threads', 'tiktok', 'pinterest',
                              'twitter', 'reddit', 'vimeo', 'dailymotion', 'twitch']

        failed_platforms = []
        expired_platforms = []
        success_platforms = []

        # اختبار كل منصة على حدة
        for platform in platforms_to_check:
            platform_status = status.get(platform, {})

            if not platform_status.get('exists', False):
                # الكوكيز غير موجودة أصلاً
                continue

            # فحص العمر
            age_days = platform_status.get('age_days', 0)
            if age_days > 30:
                expired_platforms.append({
                    'platform': platform,
                    'age_days': age_days,
                    'last_validated': platform_status.get('last_validated', 'Never')
                })

            # اختبار صلاحية الكوكيز
            logger.info(f"🔍 اختبار كوكيز {platform}...")
            is_valid = await cookie_manager.validate_cookies(platform)

            if is_valid:
                success_platforms.append(platform)
                logger.info(f"✅ {platform}: الكوكيز صالحة")
            else:
                failed_platforms.append(platform)
                logger.error(f"❌ {platform}: الكوكيز فاشلة")
                # حذف الكوكيز الفاشلة
                cookie_manager.delete_cookies(platform)

        # إرسال تقرير شامل للأدمن
        report_message = f"🍪 **تقرير فحص الكوكيز اليومي**\n"
        report_message += f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # المنصات الناجحة
        if success_platforms:
            report_message += f"✅ **الكوكيز الصالحة** ({len(success_platforms)}):\n"
            for platform in success_platforms:
                platform_info = status.get(platform, {})
                age = platform_info.get('age_days', 0)
                report_message += f"  • {platform.capitalize()}: {age} يوم\n"
            report_message += "\n"

        # المنصات الفاشلة
        if failed_platforms:
            report_message += f"❌ **الكوكيز الفاشلة** ({len(failed_platforms)}):\n"
            for platform in failed_platforms:
                report_message += f"  • {platform.capitalize()}: تم الحذف تلقائياً\n"
            report_message += "\n⚠️ **يرجى رفع كوكيز جديدة للمنصات الفاشلة!**\n\n"

        # المنصات القديمة
        if expired_platforms:
            report_message += f"⚠️ **الكوكيز القديمة** (أكثر من 30 يوم):\n"
            for platform_data in expired_platforms:
                report_message += f"  • {platform_data['platform'].capitalize()}: {platform_data['age_days']} يوم\n"
            report_message += "\n💡 يُنصح بتحديث هذه الكوكيز قريباً\n\n"

        # إحصائيات عامة
        total_checked = len(success_platforms) + len(failed_platforms)
        if total_checked > 0:
            success_rate = (len(success_platforms) / total_checked) * 100
            report_message += f"📊 **الإحصائيات:**\n"
            report_message += f"  • تم الفحص: {total_checked} منصة\n"
            report_message += f"  • معدل النجاح: {success_rate:.1f}%\n"

        # إرسال التقرير لجميع الأدمنز
        for admin_id in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=report_message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"❌ فشل إرسال التقرير للأدمن {admin_id}: {e}")

        logger.info("✅ اكتمل الفحص اليومي للـ cookies بنجاح")

    except Exception as e:
        logger.error(f"❌ فشل الفحص اليومي للـ cookies: {e}")

        # إرسال تنبيه بالخطأ للأدمن
        try:
            admin_ids_str = os.getenv("ADMIN_IDS", "")
            admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

            error_message = (
                f"🔴 **خطأ في فحص الكوكيز اليومي**\n\n"
                f"❌ الخطأ: `{str(e)}`\n"
                f"📅 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"⚠️ يرجى فحص السجلات للمزيد من التفاصيل"
            )

            for admin_id in admin_ids:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=error_message,
                    parse_mode='Markdown'
                )
        except:
            pass


async def backup_cookies_weekly(context):
    """
    مهمة النسخ الاحتياطي الأسبوعي للـ cookies
    يتم استدعاؤها تلقائياً كل 7 أيام
    """
    try:
        from handlers.cookie_manager import create_backup

        logger.info("💾 بدء النسخ الاحتياطي الأسبوعي للـ cookies...")

        # Create backup
        backup_path, file_hash = create_backup()

        if backup_path and file_hash:
            # Get log channel ID
            log_channel_id = os.getenv("LOG_CHANNEL_ID")

            if log_channel_id:
                # Send backup to log channel
                caption = (
                    "🔐 **Weekly Cookie Backup**\n\n"
                    f"📦 File: {os.path.basename(backup_path)}\n"
                    f"🔑 AES-256 Encrypted\n"
                    f"🔒 SHA256: `{file_hash[:16]}...`\n\n"
                    f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"⚠️ Admins only - Keep secure!"
                )

                with open(backup_path, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=log_channel_id,
                        document=f,
                        caption=caption,
                        parse_mode='Markdown'
                    )

                logger.info("✅ تم إرسال النسخ الاحتياطي إلى قناة السجلات بنجاح")
            else:
                logger.warning("⚠️ LOG_CHANNEL_ID غير محدد، لن يتم رفع النسخ الاحتياطي")

        else:
            logger.error("❌ فشل إنشاء النسخ الاحتياطي")

    except Exception as e:
        logger.error(f"❌ فشل النسخ الاحتياطي الأسبوعي: {e}")


def setup_cookie_check_job(application):
    """
    إعداد مهمة الفحص اليومي للـ cookies (محدثة من الفحص الأسبوعي)
    يتم استدعاؤها من bot.py عند بدء التشغيل

    Features:
    - فحص يومي للكوكيز بدلاً من أسبوعي
    - نسخ احتياطي أسبوعي (يوم الأحد)
    - تنبيهات فورية للأدمن عند الفشل

    Args:
        application: كائن Application من python-telegram-bot
    """
    from datetime import time

    job_queue = application.job_queue

    if job_queue:
        # ⭐ فحص يومي للكوكيز كل يوم في الساعة 00:00 بتوقيت UTC
        job_queue.run_daily(
            check_cookies_daily,
            time=time(hour=0, minute=0, second=0),
            name='daily_cookie_check'
        )
        logger.info("✅ تم جدولة الفحص اليومي للـ cookies (كل يوم في منتصف الليل)")

        # النسخ الاحتياطي الأسبوعي كل يوم أحد في الساعة 00:30 UTC
        job_queue.run_daily(
            backup_cookies_weekly,
            time=time(hour=0, minute=30, second=0),
            days=(6,),  # Sunday = 6 in python-telegram-bot (0=Monday)
            name='weekly_cookie_backup'
        )
        logger.info("✅ تم جدولة النسخ الاحتياطي الأسبوعي للـ cookies (كل يوم أحد)")

    else:
        logger.warning("⚠️ job_queue غير متاح، لن يتم جدولة المهام اليومية للـ cookies")


# ═══════════════════════════════════════════════════════════════
#  Error Tracking & Daily Error Reports for Admins
# ═══════════════════════════════════════════════════════════════

async def send_error_logs_to_admin(context):
    """
    إرسال سجلات الأخطاء اليومية للأدمن

    Features:
    - تجميع جميع أخطاء اليوم
    - تصنيف الأخطاء حسب النوع
    - إرسال تقرير مفصل للأدمن
    - حذف الأخطاء القديمة تلقائياً
    """
    try:
        from core.utils.error_tracker import ErrorTracker
        from datetime import datetime

        logger.info("📊 بدء إرسال تقرير الأخطاء اليومي...")

        # Get admin IDs from environment
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

        if not admin_ids:
            logger.warning("⚠️ لا توجد معرفات أدمن، لن يتم إرسال التقارير")
            return

        # الحصول على إحصائيات الأخطاء لآخر 24 ساعة
        stats = ErrorTracker.get_error_stats(hours=24)

        if stats['total'] == 0:
            # لا توجد أخطاء - إرسال تقرير إيجابي
            report_message = (
                f"✅ **تقرير الأخطاء اليومي**\n\n"
                f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"🎉 **لا توجد أخطاء في آخر 24 ساعة!**\n\n"
                f"💚 النظام يعمل بكفاءة عالية"
            )
        else:
            # توجد أخطاء - إرسال تقرير مفصل
            report_message = (
                f"🔴 **تقرير الأخطاء اليومي**\n\n"
                f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"📊 **إجمالي الأخطاء:** {stats['total']}\n\n"
            )

            # تصنيف حسب النوع
            if stats['by_type']:
                report_message += f"**حسب النوع:**\n"
                for error_type, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True):
                    report_message += f"  • {error_type}: {count}\n"
                report_message += "\n"

            # تصنيف حسب الفئة
            if stats['by_category']:
                report_message += f"**حسب الفئة:**\n"
                category_names = {
                    'unsupported_url': 'رابط غير مدعوم',
                    'private_content': 'محتوى خاص',
                    'content_not_found': 'محتوى غير موجود',
                    'timeout': 'انتهاء المهلة',
                    'network_error': 'خطأ شبكة',
                    'cookie_issue': 'مشكلة كوكيز',
                    'extractor_error': 'خطأ extractor',
                    'unknown': 'غير معروف'
                }
                for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
                    cat_name = category_names.get(category, category)
                    report_message += f"  • {cat_name}: {count}\n"
                report_message += "\n"

            # تصنيف حسب المنصة
            if stats['by_platform']:
                report_message += f"**حسب المنصة:**\n"
                for platform, count in sorted(stats['by_platform'].items(), key=lambda x: x[1], reverse=True):
                    if platform != 'unknown':
                        report_message += f"  • {platform.capitalize()}: {count}\n"
                report_message += "\n"

            # الأخطاء الأخيرة (آخر 5)
            recent_errors = ErrorTracker.get_recent_errors(limit=5)
            if recent_errors:
                report_message += f"**آخر الأخطاء:**\n"
                for i, error in enumerate(recent_errors[-5:], 1):
                    error_msg = error.get('error_message', 'N/A')
                    if len(error_msg) > 60:
                        error_msg = error_msg[:60] + "..."
                    error_type = error.get('error_type', 'unknown')
                    report_message += f"{i}. [{error_type}] {error_msg}\n"

        # إرسال التقرير لجميع الأدمنز
        for admin_id in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=report_message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"❌ فشل إرسال تقرير الأخطاء للأدمن {admin_id}: {e}")

        logger.info("✅ اكتمل إرسال تقرير الأخطاء اليومي بنجاح")

    except Exception as e:
        logger.error(f"❌ فشل إرسال تقرير الأخطاء اليومي: {e}")


def setup_error_tracking_job(application):
    """
    إعداد مهمة إرسال تقارير الأخطاء اليومية

    Args:
        application: كائن Application من python-telegram-bot
    """
    from datetime import time

    job_queue = application.job_queue

    if job_queue:
        # إرسال تقرير الأخطاء يومياً في الساعة 23:00 UTC
        job_queue.run_daily(
            send_error_logs_to_admin,
            time=time(hour=23, minute=0, second=0),
            name='daily_error_report'
        )
        logger.info("✅ تم جدولة إرسال تقرير الأخطاء اليومي (كل يوم في 23:00 UTC)")
    else:
        logger.warning("⚠️ job_queue غير متاح، لن يتم جدولة تقارير الأخطاء")


# ═══════════════════════════════════════════════════════════════
#  Temporary Files Cleanup System
# ═══════════════════════════════════════════════════════════════

def cleanup_temp_files():
    """تنظيف الملفات المؤقتة عند إيقاف البوت"""
    import glob

    try:
        cleaned_count = 0

        # تنظيف ملفات الفيديو المؤقتة
        for temp_file in glob.glob("videos/*"):
            try:
                if os.path.isfile(temp_file):
                    os.remove(temp_file)
                    cleaned_count += 1
            except Exception as e:
                logger.debug(f"تعذر حذف {temp_file}: {e}")

        # تنظيف ملفات الكوكيز المؤقتة
        for temp_file in glob.glob("cookies/*.txt"):
            try:
                if os.path.isfile(temp_file):
                    os.remove(temp_file)
                    cleaned_count += 1
            except Exception as e:
                logger.debug(f"تعذر حذف {temp_file}: {e}")

        logger.info(f"🗑️ تم تنظيف {cleaned_count} ملف مؤقت")
        return cleaned_count

    except Exception as e:
        logger.error(f"❌ فشل تنظيف الملفات المؤقتة: {e}")
        return 0


def cleanup_old_files(max_age_hours: int = 24):
    """
    تنظيف الملفات القديمة (أكبر من max_age_hours ساعة)

    Args:
        max_age_hours: العمر الأقصى للملفات بالساعات (افتراضي: 24 ساعة)
    """
    import glob

    try:
        current_time = time()
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0

        # تنظيف ملفات الفيديو القديمة
        for temp_file in glob.glob("videos/*"):
            try:
                if os.path.isfile(temp_file):
                    file_age = current_time - os.path.getmtime(temp_file)
                    if file_age > max_age_seconds:
                        os.remove(temp_file)
                        cleaned_count += 1
            except Exception as e:
                logger.debug(f"تعذر حذف {temp_file}: {e}")

        # تنظيف ملفات الكوكيز القديمة
        for temp_file in glob.glob("cookies/*.txt"):
            try:
                if os.path.isfile(temp_file):
                    file_age = current_time - os.path.getmtime(temp_file)
                    if file_age > max_age_seconds:
                        os.remove(temp_file)
                        cleaned_count += 1
            except Exception as e:
                logger.debug(f"تعذر حذف {temp_file}: {e}")

        if cleaned_count > 0:
            logger.info(f"🗑️ تم تنظيف {cleaned_count} ملف أقدم من {max_age_hours} ساعة")

        return cleaned_count

    except Exception as e:
        logger.error(f"❌ فشل تنظيف الملفات القديمة: {e}")
        return 0


# تسجيل دالة التنظيف عند إغلاق البوت
import atexit
atexit.register(cleanup_temp_files)
