import os
import asyncio
import time
import requests
import subprocess
import re
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TimedOut, NetworkError
from datetime import datetime
import yt_dlp
from yt_dlp.utils import DownloadError
import logging
import httpx

# ملاحظة: yt-dlp يقوم بتحميل الـ plugins تلقائياً من مجلد yt_dlp_plugins
# لا حاجة للتسجيل اليدوي للـ extractors

# ThreadPoolExecutor for async subprocess execution
# Performance optimization: increased from 5 to 20 workers for faster FFmpeg processing
executor = ThreadPoolExecutor(max_workers=20)

# ===== Per-user cancel download support =====
ACTIVE_DOWNLOADS = {}  # user_id -> asyncio.Task
# Performance optimization: increased from 2 to 5 concurrent downloads per user
USER_SEMAPHORE = defaultdict(lambda: asyncio.Semaphore(5))  # max 5 concurrent per user
PLAYLISTS = {}  # user_id -> {entries: list, quality: str, progress_msg: Message}
CANCEL_MESSAGES = {}  # user_id -> Message (for updating progress)
SELECTED_VIDEOS = defaultdict(set)  # user_id -> set of selected video indices

# ===== Batch YouTube download support =====
YOUTUBE_REGEX = re.compile(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+))')
BATCH_MAX_URLS = 6
# Performance optimization: increased from 2 to 5 for faster batch downloads
PER_USER_BATCH_CONCURRENCY = 5

# ===== Server Load Monitoring (V5.0.1) =====
from collections import deque
LIMIT_REJECTIONS = deque(maxlen=50)  # Track last 50 rejections with timestamps
LOAD_ALERT_THRESHOLD = 5  # Alert after 5 rejections
LOAD_ALERT_WINDOW = 600  # Within 10 minutes (600 seconds)
LAST_LOAD_ALERT = 0  # Timestamp of last alert to avoid spam

from database import (
    is_subscribed,
    get_user,
    increment_download_count,
    get_user_language,
    is_admin,
    get_daily_download_count,
    get_no_logo_credits,
    use_no_logo_credit
)

# نظام تتبع الأخطاء المتقدم
from core.utils.error_tracker import ErrorTracker, track_download_error
from utils import (
    get_message, clean_filename, get_config, format_file_size, format_duration,
    send_video_report, rate_limit, validate_url, log_warning,
    get_cached_user_data, clear_user_cache
)
from core.utils.helpers import safe_edit_message

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")  # للفشل والأخطاء
VIDEOS_CHANNEL_ID = os.getenv("VIDEOS_CHANNEL_ID")  # للنجاح والفيديوهات (تم تغيير الاسم من LOG_CHANNEL_ID_VIDEOS)
VIDEO_PATH = 'videos'

if not os.path.exists(VIDEO_PATH):
    os.makedirs(VIDEO_PATH)


# ═══════════════════════════════════════════════════════════════
#  Server Load Monitoring System (V5.0.1)
# ═══════════════════════════════════════════════════════════════

async def track_limit_rejection(context: ContextTypes.DEFAULT_TYPE, user_id: int, duration_minutes: float, limit_minutes: int, url: str):
    """
    Track when users are rejected due to time limit and alert admins if server load is high

    Args:
        context: Bot context
        user_id: User ID who was rejected
        duration_minutes: Duration of video they tried to download
        limit_minutes: Current time limit
        url: Video URL
    """
    global LAST_LOAD_ALERT

    try:
        current_time = time.time()

        # Add rejection to tracking deque
        LIMIT_REJECTIONS.append({
            'timestamp': current_time,
            'user_id': user_id,
            'duration': duration_minutes,
            'limit': limit_minutes,
            'url': url
        })

        # Log to file
        os.makedirs('logs', exist_ok=True)
        with open('logs/limit_events.log', 'a', encoding='utf-8') as f:
            log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{log_time}] User {user_id} rejected - tried {duration_minutes:.1f}min (limit={limit_minutes}min) - URL: {url[:50]}...\n")

        # Count recent rejections within the time window
        recent_rejections = [
            r for r in LIMIT_REJECTIONS
            if current_time - r['timestamp'] <= LOAD_ALERT_WINDOW
        ]

        # Check if we should alert admins
        if len(recent_rejections) >= LOAD_ALERT_THRESHOLD:
            # Avoid spamming - only alert once per 30 minutes
            if current_time - LAST_LOAD_ALERT > 1800:  # 30 minutes
                LAST_LOAD_ALERT = current_time

                # Send alert to admins
                admin_ids_str = os.getenv("ADMIN_IDS", "")
                admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

                alert_message = (
                    "⚠️ **تحذير: ضغط عالي على السيرفر!**\n\n"
                    f"تم رفض **{len(recent_rejections)} طلبات تحميل** خلال آخر {LOAD_ALERT_WINDOW//60} دقائق\n"
                    f"بسبب تجاوز الحد الزمني ({limit_minutes} دقيقة)\n\n"
                    f"💡 **الإجراءات الممكنة:**\n"
                    f"• زيادة الحد الزمني مؤقتاً\n"
                    f"• ترقية موارد السيرفر\n"
                    f"• مراقبة الاستخدام\n\n"
                    f"📊 **إحصائيات:**\n"
                    f"• متوسط مدة الفيديوهات المرفوضة: {sum(r['duration'] for r in recent_rejections)/len(recent_rejections):.1f} دقيقة\n"
                    f"• أعلى مدة: {max(r['duration'] for r in recent_rejections):.1f} دقيقة"
                )

                for admin_id in admin_ids:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=alert_message,
                            parse_mode='Markdown'
                        )
                        logger.info(f"✅ Sent load alert to admin {admin_id}")
                    except Exception as e:
                        logger.error(f"Failed to send load alert to admin {admin_id}: {e}")

                # Also log to file
                with open('logs/limit_events.log', 'a', encoding='utf-8') as f:
                    f.write(f"[{log_time}] LOAD ALERT: {len(recent_rejections)} rejections in {LOAD_ALERT_WINDOW//60} minutes\n")

    except Exception as e:
        logger.error(f"Error in track_limit_rejection: {e}")

def get_platform_from_url(url: str) -> str:
    """تحديد المنصة من رابط الفيديو - يدعم جميع المنصات الرئيسية"""
    url_lower = url.lower()

    # المنصات الأساسية
    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    elif 'facebook.com' in url_lower or 'fb.watch' in url_lower or 'fb.com' in url_lower:
        return 'facebook'
    elif 'instagram.com' in url_lower:
        return 'instagram'
    elif 'tiktok.com' in url_lower or 'vm.tiktok.com' in url_lower or 'vt.tiktok.com' in url_lower:
        return 'tiktok'
    elif 'threads.net' in url_lower or 'threads.com' in url_lower:
        return 'threads'
    elif 'pinterest.com' in url_lower or 'pin.it' in url_lower:
        return 'pinterest'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'twitter'
    # ⭐ منصات إضافية
    elif 'reddit.com' in url_lower or 'redd.it' in url_lower:
        return 'reddit'
    elif 'vimeo.com' in url_lower:
        return 'vimeo'
    elif 'dailymotion.com' in url_lower or 'dai.ly' in url_lower:
        return 'dailymotion'
    elif 'twitch.tv' in url_lower:
        return 'twitch'
    else:
        # yt-dlp يدعم أكثر من 1000 موقع، فنعتبرها "unknown" ونتركها تحاول
        return 'unknown'

def is_adult_content(url: str, title: str = "") -> bool:
    """التحقق من المحتوى الإباحي"""
    config = get_config()
    
    blocked_domains = config.get("BLOCKED_DOMAINS", [])
    for domain in blocked_domains:
        if domain.lower() in url.lower():
            return True
    
    adult_keywords = config.get("ADULT_CONTENT_KEYWORDS", [])
    text_to_check = (url + " " + title).lower()
    
    for keyword in adult_keywords:
        if keyword.lower() in text_to_check:
            return True
    
    return False

def safe_filename(title: str, max_length: int = 60) -> str:
    """
    تنظيف اسم الملف من الرموز الخطرة وتقصيره

    Args:
        title: عنوان الملف الأصلي
        max_length: الحد الأقصى لطول الاسم (افتراضي 60 حرف)

    Returns:
        اسم ملف آمن ومقصر
    """
    # إزالة الرموز الخاصة والخطرة
    safe_name = re.sub(r'[\\/*?:"<>|]', '', title)
    # إزالة المسافات الزائدة
    safe_name = ' '.join(safe_name.split())
    # تقصير الاسم
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length].rsplit(' ', 1)[0]  # قطع عند آخر مسافة
    return safe_name.strip()

async def send_log_to_channel(context: ContextTypes.DEFAULT_TYPE, update: Update, user, video_info: dict, file_path: str, sent_message, is_audio: bool = False):
    """إرسال سجل التحميل الناجح إلى قناة الفيديوهات مع رسالة نصية قابلة للنسخ (فيديو أو صوت)"""
    if not VIDEOS_CHANNEL_ID:
        logger.warning("⚠️ VIDEOS_CHANNEL_ID غير محدد، لن يتم إرسال سجلات النجاح")
        logger.warning("💡 أضف VIDEOS_CHANNEL_ID إلى ملف .env لتفعيل إرسال الفيديوهات للقناة")
        return

    try:
        log_channel_id = int(VIDEOS_CHANNEL_ID)
    except (ValueError, TypeError):
        logger.error(f"❌ VIDEOS_CHANNEL_ID غير صحيح: {VIDEOS_CHANNEL_ID}")
        return

    user_id = user.id
    user_name = user.full_name
    username = f"@{user.username}" if user.username else "مجهول"

    media_title = video_info.get('title', 'غير متوفر (No title)')
    media_url = video_info.get('webpage_url', 'N/A')
    duration = video_info.get('duration', 0)
    view_count = video_info.get('view_count') or 0
    like_count = video_info.get('like_count') or 0

    # تحديد نوع الوسائط
    media_type = "🎧 صوت" if is_audio else "🎥 فيديو"
    media_emoji = "🎧" if is_audio else "🎥"
    media_text = "صوت" if is_audio else "فيديو"

    # تنسيق عدد المشاهدات والإعجابات
    if view_count > 0:
        if view_count >= 1_000_000:
            views_text = f"{view_count / 1_000_000:.1f}M views"
        elif view_count >= 1_000:
            views_text = f"{view_count / 1_000:.1f}K views"
        else:
            views_text = f"{view_count} views"
    else:
        views_text = "N/A"

    if like_count > 0:
        if like_count >= 1_000_000:
            likes_text = f"{like_count / 1_000_000:.1f}M reactions"
        elif like_count >= 1_000:
            likes_text = f"{like_count / 1_000:.1f}K reactions"
        else:
            likes_text = f"{like_count} reactions"
    else:
        likes_text = "N/A"

    # تنسيق المدة
    if duration > 0:
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        duration_text = f"{minutes:02d}:{seconds:02d}"
    else:
        duration_text = "00:00"

    # حساب حجم الملف
    try:
        file_size_bytes = os.path.getsize(file_path)
        size_kb = file_size_bytes / 1024
        size_mb = file_size_bytes / (1024 * 1024)

        if size_mb >= 1:
            size_text = f"{size_mb:.2f} MB"
        else:
            size_text = f"{size_kb:.2f} KB"
    except:
        size_text = "N/A"

    # الوقت بتنسيق DD-MM-YYYY — HH:MM UTC
    timestamp = datetime.utcnow().strftime('%d-%m-%Y — %H:%M UTC')

    try:
        # 1) تحويل الرسالة (forward) إلى قناة السجلات لتوفير bandwidth
        forwarded = await context.bot.forward_message(
            chat_id=log_channel_id,
            from_chat_id=update.effective_chat.id,
            message_id=sent_message.message_id
        )

        # 2) إرسال رسالة تفاصيل كاملة بعد الفيديو المحول
        # Escape HTML special characters
        import html
        safe_title = html.escape(media_title)
        safe_username = html.escape(username)
        safe_user_name = html.escape(user_name)

        info_text = (
            f"{media_emoji} <b>سجل {media_text} جديد</b>\n"
            f"{'━' * 30}\n\n"
            f"👤 <b>المستخدم:</b>\n"
            f"   • الاسم: {safe_user_name}\n"
            f"   • اليوزر: {safe_username}\n"
            f"   • ID: <code>{user_id}</code>\n\n"
            f"🔗 <b>الرابط الأصلي:</b>\n{media_url}\n\n"
            f"🎞️ <b>العنوان:</b>\n{safe_title}\n\n"
            f"📊 <b>الإحصائيات:</b>\n"
            f"   • المشاهدات: {views_text}\n"
            f"   • التفاعلات: {likes_text}\n"
            f"   • المدة: {duration_text}\n"
            f"   • الحجم: {size_text}\n\n"
            f"🎭 <b>النوع:</b> {media_type}\n"
            f"📅 <b>التاريخ:</b> {timestamp}\n"
            f"{'━' * 30}\n"
            f"✅ <b>تم المعالجة بنجاح</b>"
        )

        await context.bot.send_message(
            chat_id=log_channel_id,
            text=info_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        logger.info(f"✅ تم تحويل {media_text} وإرسال التفاصيل الكاملة إلى قناة الفيديوهات (LOG_CHANNEL_ID_VIDEOS)")

    except Exception as e:
        log_warning(f"❌ فشل إرسال {media_text} إلى قناة الفيديوهات: {e}", module="handlers/download.py")

async def show_quality_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, info_dict: dict):
    """عرض قائمة اختيار الجودة - مبسطة"""
    user_id = update.effective_user.id
    lang = get_user_language(user_id)
    
    title = info_dict.get('title', 'فيديو')[:50]
    duration = format_duration(info_dict.get('duration', 0))
    
    context.user_data['pending_download'] = {
        'url': url,
        'info': info_dict
    }
    
    keyboard = [
        [InlineKeyboardButton("🌟 أفضل جودة", callback_data="quality_best")],
        [InlineKeyboardButton("📱 جودة متوسطة (أسرع)", callback_data="quality_medium")],
        [InlineKeyboardButton("🎵 صوت فقط MP3", callback_data="quality_audio")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        f"📺 اختر الجودة:\n\n"
        f"🎬 {title}\n"
        f"⏱️ {duration}"
    )
    
    await update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    )

async def handle_quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الجودة"""
    query = update.callback_query
    await query.answer()

    quality_choice = query.data.replace("quality_", "")

    pending_data = context.user_data.get('pending_download')
    if not pending_data:
        await query.edit_message_text("❌ انتهت صلاحية الطلب. أرسل الرابط مرة أخرى.")
        return

    url = pending_data['url']
    info_dict = pending_data['info']

    # === فحص مدة الفيديو لجميع الأنواع (صوت وفيديو) ===
    user_id = query.from_user.id
    from database import is_subscribed, is_admin, get_free_time_limit

    duration_seconds = info_dict.get('duration', 0)

    # فحص حد المدة الزمنية (للمستخدمين غير VIP وغير الأدمن)
    # يطبق دائماً بغض النظر عن حالة نظام الاشتراكات
    if not is_subscribed(user_id) and not is_admin(user_id):
        if duration_seconds > 0:
            duration_minutes = duration_seconds / 60
            time_limit_minutes = get_free_time_limit()

            # -1 يعني غير محدود
            if time_limit_minutes != -1 and duration_minutes > time_limit_minutes:
                logger.info(f"🚫 رفض تحميل - المدة {duration_minutes:.1f}min > الحد {time_limit_minutes}min للمستخدم {user_id}")
                keyboard = [[InlineKeyboardButton(
                    "⭐ اشترك في VIP للتحميل غير المحدود",
                    url="https://instagram.com/7kmmy"
                )]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    f"🚫 **لا يمكنك تحميل مقاطع أطول من {time_limit_minutes} دقيقة!**\n\n"
                    f"⏱️ مدة المقطع: {duration_minutes:.1f} دقيقة\n"
                    f"🔒 الحد المسموح: {time_limit_minutes} دقيقة\n\n"
                    f"💎 **اشترك في VIP للحصول على تحميل غير محدود!**",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return

    # التحقق من مدة الصوتيات إذا اختار المستخدم "صوت فقط"
    if quality_choice == 'audio':
        from database import is_audio_enabled

        # التحقق من تفعيل الصوتيات
        if not is_audio_enabled():
            await query.edit_message_text(
                "🚫 **تحميل الصوتيات معطل حالياً!**\n\n"
                "يرجى اختيار جودة فيديو بدلاً من ذلك."
            )
            return

        # فحص مطلق: منع تحميل الصوتيات الطويلة جداً (>20 دقيقة) للجميع لتجنب مشاكل الأداء
        duration_seconds = info_dict.get('duration', 0)
        if duration_seconds > 1200:  # 20 دقيقة = 1200 ثانية
            duration_minutes = duration_seconds / 60
            await query.edit_message_text(
                f"⚠️ **الملف طويل جداً للتحميل كصوت!**\n\n"
                f"⏱️ مدة المقطع: {duration_minutes:.1f} دقيقة ({duration_seconds/3600:.1f} ساعة)\n"
                f"🔒 الحد الأقصى: 20 دقيقة\n\n"
                f"💡 **سبب الحد:**\n"
                f"• استخراج الصوت من ملفات طويلة يستغرق وقتاً طويلاً (>10 دقائق)\n"
                f"• حجم الملف الناتج قد يتجاوز حد Telegram (50MB)\n"
                f"• قد يتسبب في مشاكل في الرفع والتحميل\n\n"
                f"📹 جرب تحميله كفيديو بدلاً من ذلك!",
                parse_mode='Markdown'
            )
            return

        # التحقق من حد المدة (فقط إذا كان الاشتراك مفعلاً)
        subscription_enabled = is_subscription_enabled()

        if subscription_enabled and not is_subscribed(user_id) and not is_admin(user_id):
            duration_seconds = info_dict.get('duration', 0)

            if duration_seconds > 0:
                duration_minutes = duration_seconds / 60
                audio_limit_minutes = get_free_time_limit()  # استخدام نفس الحد الزمني العام

                # -1 يعني غير محدود، فلا نحتاج للتحقق
                if audio_limit_minutes != -1 and duration_minutes > audio_limit_minutes:
                    keyboard = [[InlineKeyboardButton(
                        "⭐ اشترك في VIP للتحميل غير المحدود",
                        url="https://instagram.com/7kmmy"
                    )]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🚫 **لا يمكنك تحميل مقاطع صوتية أطول من {audio_limit_minutes} دقيقة!**\n\n"
                        f"⏱️ مدة المقطع: {duration_minutes:.1f} دقيقة\n"
                        f"🔒 الحد المسموح: {audio_limit_minutes} دقيقة\n\n"
                        f"💎 **اشترك في VIP للحصول على تحميل غير محدود!**",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    return

    del context.user_data['pending_download']

    await query.edit_message_text("⏳ جاري التحضير...")

    await download_video_with_quality(update, context, url, info_dict, quality_choice)

def get_ydl_opts_for_platform(url: str, quality: str = 'best'):
    """
    إعدادات yt-dlp محسّنة حسب المنصة
    """
    # تحديد المنصة (V5.1 - Extended Platform Detection)
    is_facebook = 'facebook.com' in url or 'fb.watch' in url or 'fb.com' in url
    is_instagram = 'instagram.com' in url
    is_tiktok = 'tiktok.com' in url or 'vm.tiktok.com' in url or 'vt.tiktok.com' in url
    is_threads = 'threads.net' in url or 'threads.com' in url
    is_pinterest = 'pinterest.com' in url or 'pin.it' in url
    is_reddit = 'reddit.com' in url
    is_twitter = 'twitter.com' in url or 'x.com' in url
    is_vimeo = 'vimeo.com' in url
    is_dailymotion = 'dailymotion.com' in url
    is_twitch = 'twitch.tv' in url
    
    # الجودة
    quality_formats = {
        'best': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        'medium': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        'audio': 'bestaudio/best'
    }

    format_choice = quality_formats.get(quality, 'best')

    # Pinterest - لا نحدد format هنا، سيتم تحديده في الإعدادات الخاصة
    if is_pinterest and quality != 'audio':
        # سيتم تحديد format في الإعدادات الخاصة أدناه
        format_choice = None
        logger.info("🎨 Pinterest: استخدام الإعدادات الخاصة")
    # باقي المنصات المرنة (Facebook, Reddit, Twitter, Vimeo, Dailymotion, Twitch)
    elif (is_facebook or is_reddit or is_vimeo or is_dailymotion or is_twitch or is_twitter) and quality != 'audio':
        # محاولة عدة خيارات بالترتيب - مرن للغاية
        format_choice = 'best/bestvideo+bestaudio/bestvideo/b/bv*+ba/bv*/w'

    # إعدادات أساسية
    ydl_opts = {
        'outtmpl': os.path.join(VIDEO_PATH, '%(title).60s.%(ext)s'),  # تقصير تلقائي لـ 60 حرف
        'quiet': False,
        'no_warnings': False,
        'extract_flat': False,
        'ignoreerrors': False,
        'nocheckcertificate': True,
        # تحسينات السرعة العامة
        'concurrent_fragment_downloads': 8,
        'retries': 20,
        'fragment_retries': 20,
        'http_chunk_size': 10485760,  # 10MB
        'buffersize': 1024 * 1024,  # 1MB
        # إعدادات التوافق العامة
        'compat_opts': ['no-youtube-unavailable-videos'],
    }

    # إضافة format فقط إذا كان محدداً (بعض المنصات تحتاج auto selection)
    if format_choice is not None:
        ydl_opts['format'] = format_choice

    # دعم cookies - Auto-Detection V5.1 with Platform Linking
    cookies_loaded = False

    # محاولة تحميل cookies للمنصات الاجتماعية مع دعم الربط (V5.1)
    if is_tiktok or is_instagram or is_facebook or is_threads or is_pinterest or is_reddit or is_twitter or is_vimeo or is_dailymotion or is_twitch:
        # 1️⃣ Try encrypted cookies first (V5.1 with Platform Linking)
        try:
            from handlers.cookie_manager import cookie_manager, PLATFORM_COOKIE_LINKS

            # Detect platform with linking support
            platform = None
            if is_tiktok:
                platform = 'tiktok'
            elif is_facebook:
                platform = 'facebook'
            elif is_instagram:
                platform = 'instagram'
            elif is_threads:
                platform = 'threads'  # Threads uses Instagram cookies (Meta)
            elif is_pinterest:
                platform = 'pinterest'  # Links to Instagram
            elif is_reddit:
                platform = 'reddit'  # Links to Facebook
            elif is_twitter:
                platform = 'twitter'  # Links to General
            elif is_vimeo:
                platform = 'vimeo'  # Links to General
            elif is_dailymotion:
                platform = 'dailymotion'  # Links to General
            elif is_twitch:
                platform = 'twitch'  # Links to General

            if platform:
                # Get the actual cookie file (handles linking)
                cookie_file = PLATFORM_COOKIE_LINKS.get(platform.lower())

                if cookie_file:
                    # Try to decrypt and use encrypted cookies
                    cookie_path = cookie_manager.decrypt_cookie_file(cookie_file)
                    if cookie_path:
                        # التحقق من وجود الملف فعلاً
                        if os.path.exists(cookie_path):
                            ydl_opts['cookiefile'] = cookie_path
                            cookies_loaded = True

                            # قراءة عدد الكوكيز للتأكد من صحة الملف
                            try:
                                with open(cookie_path, 'r') as f:
                                    cookie_lines = [line for line in f if line.strip() and not line.startswith('#')]
                                    logger.info(f"📝 عدد الكوكيز في الملف: {len(cookie_lines)}")
                            except Exception as read_err:
                                logger.warning(f"⚠️ لا يمكن قراءة ملف الكوكيز: {read_err}")

                            if cookie_file != platform:
                                logger.info(f"✅ Using encrypted {cookie_file} cookies for {platform} (V5.1 Linked) - Path: {cookie_path}")
                            else:
                                logger.info(f"✅ Using encrypted cookies for {platform} (V5.1) - Path: {cookie_path}")
                        else:
                            logger.error(f"❌ ملف الكوكيز غير موجود: {cookie_path}")
        except Exception as e:
            logger.debug(f"Could not load encrypted cookies: {e}")

        # 2️⃣ Try browser cookies if encrypted cookies not available (silent fallback)
        if not cookies_loaded:
            # محاولة Chrome (بشكل صامت مع اختبار فعلي)
            try:
                from yt_dlp.cookies import extract_cookies_from_browser
                # اختبار استخراج cookies من Chrome فعلياً
                test_cookies = extract_cookies_from_browser('chrome')
                if test_cookies:
                    ydl_opts['cookiesfrombrowser'] = ('chrome',)
                    cookies_loaded = True
                    logger.info("✅ Using cookies from Chrome browser")
            except Exception as e:
                logger.debug(f"Chrome browser cookies not available: {e}")
                pass  # تجاهل أخطاء Chrome بالكامل

            # محاولة Firefox إذا فشل Chrome
            if not cookies_loaded:
                try:
                    from yt_dlp.cookies import extract_cookies_from_browser
                    # اختبار استخراج cookies من Firefox فعلياً
                    test_cookies = extract_cookies_from_browser('firefox')
                    if test_cookies:
                        ydl_opts['cookiesfrombrowser'] = ('firefox',)
                        cookies_loaded = True
                        logger.info("✅ Using cookies from Firefox browser")
                except Exception as e:
                    logger.debug(f"Firefox browser cookies not available: {e}")
                    pass  # تجاهل أخطاء Firefox بالكامل

        # 3️⃣ محاولة تحميل ملفات cookies.txt خاصة بكل منصة (fallback)
        if not cookies_loaded:
            platform_cookies = None
            if is_tiktok and os.path.exists('cookies/tiktok.txt'):
                platform_cookies = 'cookies/tiktok.txt'
            elif is_facebook and os.path.exists('cookies/facebook.txt'):
                platform_cookies = 'cookies/facebook.txt'
            elif is_instagram and os.path.exists('cookies/instagram.txt'):
                platform_cookies = 'cookies/instagram.txt'

            if platform_cookies:
                ydl_opts['cookiefile'] = platform_cookies
                cookies_loaded = True
                logger.info(f"✅ Using platform-specific cookies from {platform_cookies}")

    # 4️⃣ إذا فشل تحميل cookies من المتصفح والملفات الخاصة، استخدم ملف cookies.txt العام
    if not cookies_loaded and os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'
        logger.info("✅ Using cookies.txt for authentication")
    
    # ⭐ إعدادات خاصة لـ Pinterest - حل مشاكل التحميل
    if is_pinterest:
        ydl_opts.update({
            # لا نحدد format - نترك yt-dlp يختار تلقائياً (أفضل للتوافق)
            # استخدام ffmpeg لتحميل HLS بدلاً من native downloader
            'external_downloader': 'ffmpeg',
            'external_downloader_args': {
                'ffmpeg_i': [
                    '-hide_banner',
                    '-loglevel', 'error'
                ]
            },
            # تقليل concurrent downloads لتجنب مشاكل fragments
            'concurrent_fragment_downloads': 1,
            # زيادة المحاولات
            'retries': 30,
            'fragment_retries': 30,
            # تقليل حجم buffer
            'http_chunk_size': 1048576,  # 1MB بدلاً من 10MB
            'buffersize': 1024 * 128,  # 128KB بدلاً من 512KB
            # إضافة sleep بين fragments
            'sleep_interval': 1,
            'max_sleep_interval': 3,
            # تجاهل أخطاء fragments
            'skip_unavailable_fragments': True,
            # User-Agent مهم جداً لـ Pinterest
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.pinterest.com/',
                'Origin': 'https://www.pinterest.com',
            },
            # إعدادات Pinterest الإضافية
            'extractor_args': {
                'pinterest': {
                    'timeout': 90
                }
            }
        })
        logger.info("🎬 Pinterest: استخدام ffmpeg لتحميل HLS")

    # ⭐ إعدادات خاصة لـ Reddit - حل مشاكل Conflicting Range
    elif is_reddit:
        ydl_opts.update({
            # استخدام ffmpeg لتحميل HLS/DASH بدلاً من native downloader
            'external_downloader': 'ffmpeg',
            'external_downloader_args': {
                'ffmpeg_i': [
                    '-hide_banner',
                    '-loglevel', 'error'
                ]
            },
            # تقليل concurrent downloads لتجنب مشاكل fragments
            'concurrent_fragment_downloads': 1,
            # زيادة المحاولات
            'retries': 30,
            'fragment_retries': 30,
            # تقليل حجم buffer
            'http_chunk_size': 1048576,  # 1MB بدلاً من 10MB
            'buffersize': 1024 * 128,  # 128KB
            # إضافة sleep بين fragments لتجنب rate limiting
            'sleep_interval': 0,
            'max_sleep_interval': 1,
            # تجاهل fragments غير متاحة
            'skip_unavailable_fragments': True,
            # User-Agent مهم لـ Reddit
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        })
        logger.info("🔴 Reddit: استخدام ffmpeg لتحميل HLS/DASH")

    # إعدادات خاصة لـ Facebook
    elif is_facebook:
        # فحص إذا كان story
        is_story = '/stories/' in url or '/story/' in url

        ydl_opts.update({
            'format': 'best',  # Facebook يحتاج 'best' فقط
            # 🎯 لا نقيد extractors - دع yt-dlp يجرب جميع الخيارات
            # 'allowed_extractors' تسبب "No suitable extractor" لأن facebook extractor لا يدعم Stories
            'extractor_args': {
                'facebook': {
                    'timeout': 90 if is_story else 60,  # timeout أطول للستوريات
                    'app_id': '87741124305',  # Facebook app_id للوصول إلى API
                    'use_hacks': ['headers', 'graphql'] if is_story else ['headers']  # graphql للستوريات
                }
            },
            # User-Agent مهم لـ Facebook
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            # إعدادات إضافية للستوريات
            'sleep_interval': 2 if is_story else 0,
            'max_sleep_interval': 5 if is_story else 0,
            'skip_unavailable_fragments': True,
        })

        # 📝 Logging للتأكد من الإعدادات
        if is_story:
            allowed = ydl_opts.get('allowed_extractors', 'No restrictions (try all)')
            logger.info(f"🔧 [Facebook Story] Extractors: {allowed}")
            logger.info(f"🔧 [Facebook Story] Cookies: {'✅ Loaded' if cookies_loaded else '❌ Not loaded'}")
            logger.info(f"🔧 [Facebook Story] Strategy: Let yt-dlp try all available extractors")

        # للستوريات: يجب أن تكون الكوكيز موجودة
        if is_story and not cookies_loaded:
            logger.warning("⚠️ Facebook stories تحتاج كوكيز! قد يفشل التحميل.")
    
    # إعدادات خاصة لـ Instagram (Stories + Reels)
    elif is_instagram:
        # فحص إذا كان story
        is_story = '/stories/' in url or '/story/' in url

        ydl_opts.update({
            'format': 'best',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'X-IG-App-ID': '936619743392459',
                'X-Instagram-AJAX': '1',
                'X-Requested-With': 'XMLHttpRequest',
            },
            'extractor_args': {
                'instagram': {
                    'timeout': 90,  # زيادة timeout للستوريات
                    'app_id': '567067343352427',
                    'use_hacks': ['headers', 'graphql']  # استخدام graphql للستوريات
                }
            },
            # إعدادات إضافية للستوريات
            'sleep_interval': 2 if is_story else 0,  # تأخير بين الطلبات للستوريات
            'max_sleep_interval': 5 if is_story else 0,
            'skip_unavailable_fragments': True,
        })

        # للستوريات: يجب أن تكون الكوكيز موجودة
        if is_story and not cookies_loaded:
            logger.warning("⚠️ Instagram stories تحتاج كوكيز! قد يفشل التحميل.")
    
    # إعدادات خاصة لـ TikTok - مُحسّنة للصور والفيديوهات
    elif is_tiktok:
        logger.info("🎵 [TikTok] تكوين إعدادات TikTok...")

        # إضافة tiktok-impersonate-browser إلى compat_opts
        if 'compat_opts' in ydl_opts:
            ydl_opts['compat_opts'].append('tiktok-impersonate-browser')
        else:
            ydl_opts['compat_opts'] = ['tiktok-impersonate-browser']

        logger.info(f"🎵 [TikTok] compat_opts: {ydl_opts.get('compat_opts')}")

        # إعدادات أساسية لـ TikTok
        tiktok_opts = {
            'format': 'best',
            'writesubtitles': False,
            'writethumbnail': False,
            'extractor_args': {
                'tiktok': {
                    'api_hostname': 'api16-normal-c-useast1a.tiktokv.com',
                    'player_client': ['android'],
                    'timeout': 60
                }
            }
        }

        # Browser impersonation - اختياري (يعمل إذا كان curl-cffi متوفر)
        impersonate_added = False
        try:
            import curl_cffi
            from yt_dlp.networking.impersonate import ImpersonateTarget
            logger.info("🎵 [TikTok] curl_cffi متوفر - إضافة browser impersonation...")
            # استخدام Android Chrome لأنه يعمل بشكل أفضل مع TikTok
            tiktok_opts['impersonate'] = ImpersonateTarget('chrome', '99', 'android', None)
            logger.info("✅ [TikTok] تم إضافة impersonate: chrome-99-android")
            # لا نضيف http_headers يدوياً عند استخدام impersonate
            # لأن impersonate يوفر headers تلقائياً
            impersonate_added = True
        except (ImportError, Exception) as e:
            logger.warning(f"⚠️ [TikTok] browser impersonation معطل: {str(e)}")
            logger.info("🎵 [TikTok] سيتم استخدام http_headers يدوياً")

        # إضافة http_headers فقط إذا لم يتم تفعيل impersonate
        if not impersonate_added:
            tiktok_opts['http_headers'] = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
                'Referer': 'https://www.tiktok.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            logger.info("🎵 [TikTok] تم إضافة http_headers يدوياً")

        ydl_opts.update(tiktok_opts)
    
    # إعدادات الصوت - محسّنة للسرعة 10x ⚡
    if quality == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',  # أفضل جودة صوت متاحة
            # تحسينات السرعة القصوى
            'concurrent_fragment_downloads': 16,  # زيادة إلى 16 للتوازي الأعلى
            'http_chunk_size': 10 * 1024 * 1024,  # 10MB chunks (ضعف السرعة)
            'buffersize': 4 * 1024 * 1024,  # 4MB buffer (أسرع معالجة)
            'retries': 20,  # محاولات أكثر للاستقرار
            'fragment_retries': 20,
            # تحسينات إضافية
            'external_downloader_args': ['-j', '8', '-x', '16', '-s', '16'],  # aria2c arguments للسرعة
            'prefer_ffmpeg': True,  # استخدام ffmpeg للسرعة
            'keepvideo': False,  # حذف الفيديو مباشرة بعد الاستخراج
        })
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        # إضافة FFmpeg arguments للسرعة القصوى (تقليل وقت التحويل 3-5x)
        ydl_opts['postprocessor_args'] = [
            '-threads', '0',  # استخدام جميع CPU cores المتاحة
            '-preset', 'ultrafast',  # أسرع preset ممكن
            '-movflags', '+faststart',  # تحسين streaming
        ]

    return ydl_opts


async def upload_to_server(file_path: str, user_id: int):
    """
    Placeholder function لرفع الملف إلى سيرفر خارجي
    يمكن تطويره لاحقاً للرفع على خدمات مثل:
    - Google Drive
    - Mega.nz
    - WeTransfer
    - أو أي سيرفر مخصص
    """
    # TODO: Implement actual upload logic here
    # For now, just return a placeholder URL
    logger.info(f"📤 [PLACEHOLDER] رفع الملف إلى السيرفر: {file_path} للمستخدم {user_id}")
    return f"https://example.com/files/{os.path.basename(file_path)}"


async def send_file_with_retry(context, chat_id, file_path, is_audio, caption, reply_to_message_id, duration, info_dict, max_retries=3, progress_message=None):
    """
    محاولة إرسال الملف مع إعادة المحاولة في حالة TimedOut
    يستخدم sendDocument للملفات الكبيرة (>45MB)
    مع progress tracking للرفع
    """
    # فحص حجم الملف
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / (1024 * 1024)

    # ضغط الملفات الصوتية الكبيرة جداً (>50MB) تلقائياً إلى 128kbps
    if is_audio and file_size_mb > 50:
        try:
            logger.info(f"🗜️ الملف كبير جداً ({file_size_mb:.1f}MB) - جاري الضغط إلى 128kbps...")

            # تحديث رسالة المستخدم
            if progress_message:
                await safe_edit_message(
                    progress_message,
                    f"🗜️ **جاري ضغط الملف...**\n\n"
                    f"📦 الحجم الأصلي: {file_size_mb:.1f} MB\n"
                    f"🎵 الجودة: 128 kbps\n\n"
                    f"⏳ الرجاء الانتظار...",
                    parse_mode='Markdown'
                )

            # مسار الملف المضغوط
            compressed_path = file_path.replace(".mp3", "_compressed.mp3")

            # ضغط الملف باستخدام FFmpeg (async)
            compress_cmd = [
                'ffmpeg', '-i', file_path,
                '-b:a', '128k',           # Bitrate 128kbps
                '-ar', '44100',           # Sample rate 44.1kHz
                '-ac', '2',               # Stereo
                '-threads', '0',          # Multi-threading
                '-preset', 'ultrafast',   # Fast encoding
                compressed_path,
                '-y'                      # Overwrite
            ]

            # تشغيل FFmpeg بشكل async لتجنب blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                executor,
                lambda: subprocess.run(compress_cmd, check=True, capture_output=True)
            )

            # التحقق من نجاح الضغط
            if os.path.exists(compressed_path):
                compressed_size = os.path.getsize(compressed_path)
                compressed_size_mb = compressed_size / (1024 * 1024)
                reduction = ((file_size - compressed_size) / file_size) * 100

                logger.info(f"✅ تم الضغط بنجاح: {file_size_mb:.1f}MB → {compressed_size_mb:.1f}MB (تقليل {reduction:.1f}%)")

                # حذف الملف الأصلي واستخدام المضغوط
                try:
                    os.remove(file_path)
                except:
                    pass

                file_path = compressed_path
                file_size = compressed_size
                file_size_mb = compressed_size_mb
            else:
                logger.warning(f"⚠️ فشل الضغط - سيتم استخدام الملف الأصلي")

        except Exception as e:
            logger.error(f"❌ خطأ في ضغط الملف: {e}")
            logger.info(f"ℹ️ سيتم استخدام الملف الأصلي")

    # استخدام sendDocument للملفات الكبيرة (>45MB لنكون في الجانب الآمن)
    use_document = file_size > (45 * 1024 * 1024)  # 45MB

    # تحديد timeouts حسب حجم الملف
    if use_document or file_size_mb > 40:
        # ملفات كبيرة جداً
        read_timeout = 900   # 15 دقيقة
        write_timeout = 900  # 15 دقيقة
        connect_timeout = 180
        pool_timeout = 180
    elif file_size_mb > 20:
        # ملفات متوسطة-كبيرة
        read_timeout = 600   # 10 دقائق
        write_timeout = 600
        connect_timeout = 120
        pool_timeout = 120
    else:
        # ملفات عادية
        read_timeout = 300   # 5 دقائق
        write_timeout = 300
        connect_timeout = 60
        pool_timeout = 60

    if use_document:
        logger.info(f"📦 الملف كبير ({file_size_mb:.1f}MB) - سيتم استخدام sendDocument بدلاً من send_audio/video")
    elif file_size_mb > 20:
        logger.info(f"⚠️ الملف كبير ({file_size_mb:.1f}MB) - استخدام timeouts ممتدة")

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"🔄 محاولة رفع الملف (المحاولة {attempt}/{max_retries})")

            # تحديث رسالة المستخدم بحالة الرفع
            if progress_message:
                await safe_edit_message(
                    progress_message,
                    f"📤 **جاري رفع الملف...**\n\n"
                    f"📦 الحجم: {file_size_mb:.1f} MB\n"
                    f"⏱️ قد يستغرق دقائق حسب حجم الملف\n\n"
                    f"⏳ الرجاء الانتظار...",
                    parse_mode='Markdown'
                )

            # قياس وقت الرفع بدقة
            upload_start_time = time.time()
            logger.info(f"⏱️ بدء الرفع - الوقت: {time.strftime('%H:%M:%S')}")

            with open(file_path, 'rb') as file:
                if use_document:
                    # استخدام sendDocument للملفات الكبيرة
                    sent_message = await context.bot.send_document(
                        chat_id=chat_id,
                        document=file,
                        caption=caption[:1024],
                        reply_to_message_id=reply_to_message_id,
                        read_timeout=read_timeout,
                        write_timeout=write_timeout,
                        connect_timeout=connect_timeout,
                        pool_timeout=pool_timeout
                    )
                    logger.info(f"✅ تم رفع الملف كمستند ({file_size_mb:.1f}MB)")
                elif is_audio:
                    sent_message = await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=file,
                        caption=caption[:1024],
                        reply_to_message_id=reply_to_message_id,
                        duration=duration,
                        read_timeout=read_timeout,
                        write_timeout=write_timeout,
                        connect_timeout=connect_timeout,
                        pool_timeout=pool_timeout
                    )
                else:
                    sent_message = await context.bot.send_video(
                        chat_id=chat_id,
                        video=file,
                        caption=caption[:1024],
                        reply_to_message_id=reply_to_message_id,
                        supports_streaming=True,
                        width=info_dict.get('width'),
                        height=info_dict.get('height'),
                        duration=duration,
                        read_timeout=read_timeout,
                        write_timeout=write_timeout,
                        connect_timeout=connect_timeout,
                        pool_timeout=pool_timeout
                    )

            # حساب وقت الرفع الفعلي
            upload_duration = time.time() - upload_start_time
            upload_speed = file_size_mb / upload_duration if upload_duration > 0 else 0

            logger.info(f"✅ تم الرفع بنجاح في المحاولة {attempt}")
            logger.info(f"⏱️ وقت الرفع: {upload_duration:.2f} ثانية ({upload_duration/60:.2f} دقيقة)")
            logger.info(f"📊 سرعة الرفع: {upload_speed:.2f} MB/s")

            return sent_message, None

        except (TimedOut, httpx.WriteTimeout, httpx.ReadTimeout, NetworkError) as e:
            import traceback
            error_msg = str(e)
            logger.warning(f"⏱️ TimedOut في المحاولة {attempt}/{max_retries}: {error_msg}")

            # التحقق من خطأ 413 (Request Entity Too Large)
            if '413' in error_msg or 'Request Entity Too Large' in error_msg or 'Too Large' in error_msg:
                logger.error(f"❌ [send_file_with_retry] الملف أكبر من 50MB - Telegram لا يدعم هذا الحجم!")
                logger.error(f"  - حجم الملف: {file_size_mb:.2f}MB")
                logger.error(f"  - الحد الأقصى: 50MB")
                logger.error(f"📍 [send_file_with_retry] Stack trace:\n{traceback.format_exc()}")
                return None, Exception(f"Request Entity Too Large")

            if attempt < max_retries:
                # تأخير أطول للملفات الكبيرة
                if use_document:
                    wait_time = attempt * 5  # 5، 10، 15 ثانية للملفات الكبيرة
                else:
                    wait_time = attempt * 2  # 2، 4، 6 ثانية للملفات العادية
                logger.info(f"⏳ انتظار {wait_time} ثانية قبل إعادة المحاولة...")
                await asyncio.sleep(wait_time)
            else:
                # فشلت جميع المحاولات
                logger.error(f"❌ فشلت جميع المحاولات ({max_retries}) لرفع الملف")
                logger.error(f"📍 [send_file_with_retry] Stack trace:\n{traceback.format_exc()}")
                return None, e

        except Exception as e:
            # أخطاء أخرى لا تستدعي إعادة المحاولة
            import traceback
            logger.error(f"❌ [send_file_with_retry] خطأ غير متوقع أثناء الرفع: {type(e).__name__}: {str(e)}")
            logger.error(f"📍 [send_file_with_retry] Stack trace:\n{traceback.format_exc()}")

            # التحقق من خطأ 413
            error_msg = str(e)
            if '413' in error_msg or 'Request Entity Too Large' in error_msg or 'Too Large' in error_msg:
                logger.error(f"❌ [send_file_with_retry] الملف أكبر من 50MB - Telegram لا يدعم هذا الحجم!")
                return None, Exception(f"Request Entity Too Large")

            return None, e

    return None, Exception("فشل الرفع بعد جميع المحاولات")


async def download_video_with_quality(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, info_dict: dict, quality: str):
    """تحميل الفيديو بالجودة المحددة"""
    user = update.effective_user
    user_id = user.id
    lang = get_user_language(user_id)
    
    ydl_opts = get_ydl_opts_for_platform(url, quality)
    
    await perform_download(update, context, url, info_dict, ydl_opts, is_audio=(quality=='audio'))

async def perform_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, info_dict: dict, ydl_opts: dict, is_audio: bool = False):
    """تنفيذ عملية التحميل"""
    user = update.effective_user
    user_id = user.id
    lang = get_user_language(user_id)
    
    is_user_admin = is_admin(user_id)
    is_subscribed_user = is_subscribed(user_id)
    config = get_config()

    processing_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📥 جاري التحضير...\n⏳ الرجاء الانتظار...",
        parse_mode='Markdown'
    )
    
    new_filepath = None
    temp_watermarked_path = None
    
    # التحقق إذا كان المحتوى صورة وليس فيديو
    is_image_post = False
    
    # طريقة 1: فحص duration - إذا كانت 0 قد يكون صور
    duration = info_dict.get('duration', None)
    
    # طريقة 2: فحص الصيغ المتاحة
    if 'formats' in info_dict and info_dict.get('formats'):
        has_video = any('vcodec' in fmt and fmt.get('vcodec') != 'none' 
                       for fmt in info_dict['formats'])
        has_image = any('ext' in fmt and fmt.get('ext') in ['jpg', 'jpeg', 'png', 'webp'] 
                       for fmt in info_dict['formats'])
        
        # إذا كان فيه صور وما فيه فيديو = منشور صور
        if has_image and not has_video:
            is_image_post = True
            logger.info("✅ تم اكتشاف منشور صور")
    
    # طريقة 3: فحص نوع الملف في thumbnail أو entries
    if not is_image_post and 'entries' in info_dict:
        # بعض المنصات تضع الصور في entries
        entries = info_dict.get('entries', [])
        if entries and all(e.get('ext') in ['jpg', 'jpeg', 'png', 'webp'] for e in entries if e):
            is_image_post = True
            logger.info("✅ تم اكتشاف صور في entries")
    
    # طريقة 4: فحص خاص لتيك توك
    url_lower = url.lower()
    if 'tiktok.com' in url_lower and duration == 0:
        is_image_post = True
        logger.info("✅ تيك توك بدون مدة - احتمال صور")
    
    try:
        # إذا كان منشور صور من تيك توك أو انستقرام
        if is_image_post:
            await safe_edit_message(processing_message, "📷 اكتشفت صوراً! جاري التحميل...")
            
            loop = asyncio.get_event_loop()
            
            # إعداد خاص للصور - نضيف write_all_thumbnails لتيك توك
            image_ydl_opts = ydl_opts.copy()
            image_ydl_opts.update({
                'writethumbnail': True,
                'write_all_thumbnails': True,
                'skip_download': False,
            })
            
            # تحميل الصور
            try:
                with yt_dlp.YoutubeDL(image_ydl_opts) as ydl:
                    await loop.run_in_executor(None, lambda: ydl.download([url]))
                logger.info("✅ تم تحميل المحتوى من yt-dlp")
            except Exception as e:
                log_warning(f"❌ خطأ في تحميل الصور: {e}", module="handlers/download.py")
                raise
            
            # البحث عن الصور المحملة
            image_files = []
            current_time = time.time()
            
            for file in os.listdir(VIDEO_PATH):
                file_path = os.path.join(VIDEO_PATH, file)
                # التحقق أنها صورة ومحملة حديثاً (آخر دقيقة)
                if (file.endswith(('.jpg', '.jpeg', '.png', '.webp')) and 
                    os.path.isfile(file_path) and 
                    os.path.getmtime(file_path) > (current_time - 60)):
                    image_files.append(file_path)
            
            logger.info(f"📸 تم العثور على {len(image_files)} صورة")
            
            if not image_files:
                # محاولة بديلة: تحميل thumbnail كصورة
                log_warning("⚠️ لم يتم العثور على صور، محاولة تحميل thumbnail...", module="handlers/download.py")
                thumbnail_url = info_dict.get('thumbnail')
                if thumbnail_url:
                    try:
                        import requests
                        response = requests.get(thumbnail_url, timeout=10)
                        if response.status_code == 200:
                            thumb_path = os.path.join(VIDEO_PATH, f"thumbnail_{int(time.time())}.jpg")
                            with open(thumb_path, 'wb') as f:
                                f.write(response.content)
                            image_files.append(thumb_path)
                            logger.info("✅ تم تحميل thumbnail كصورة")
                    except Exception as e:
                        log_warning(f"❌ فشل تحميل thumbnail: {e}", module="handlers/download.py")
            
            if not image_files:
                raise FileNotFoundError("لم يتم العثور على صور محملة")
            
            title = info_dict.get('title', 'صور')
            uploader = info_dict.get('uploader', 'Unknown')[:40]

            # إرسال الصور للمستخدم
            await safe_edit_message(processing_message, f"📤 جاري رفع {len(image_files)} صورة...")
            
            caption_text = (
                f"📷 {title[:50]}\n\n"
                f"👤 {uploader}\n"
                f"🖼️ عدد الصور: {len(image_files)}\n"
                f"{'💎 VIP' if is_subscribed_user else '🆓 مجاني'}\n\n"
                f"✨ بواسطة @{context.bot.username}"
            )
            
            # إرسال الصور (واحدة تلو الأخرى أو كمجموعة)
            if len(image_files) == 1:
                with open(image_files[0], 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=photo,
                        caption=caption_text[:1024],
                        reply_to_message_id=update.effective_message.message_id
                    )
            else:
                # إرسال كمجموعة (MediaGroup)
                from telegram import InputMediaPhoto
                media_group = []
                
                for idx, img_path in enumerate(image_files[:10]):  # تيليجرام يسمح بـ 10 صور كحد أقصى
                    with open(img_path, 'rb') as photo:
                        if idx == 0:
                            media_group.append(InputMediaPhoto(media=photo.read(), caption=caption_text[:1024]))
                        else:
                            media_group.append(InputMediaPhoto(media=photo.read()))
                
                await context.bot.send_media_group(
                    chat_id=update.effective_chat.id,
                    media=media_group,
                    reply_to_message_id=update.effective_message.message_id
                )
            
            logger.info(f"✅ تم إرسال {len(image_files)} صورة")
            
            try:
                await processing_message.delete()
            except:
                pass
            
            # تحديث عداد التحميلات
            if not is_user_admin and not is_subscribed_user:
                from database import get_daily_download_limit_setting
                increment_download_count(user_id)
                daily_limit = get_daily_download_limit_setting()
                remaining = daily_limit - get_daily_download_count(user_id)
                if remaining > 0:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"ℹ️ تبقى لك {remaining} تحميلات مجانية اليوم"
                    )
            
            # حذف الصور المؤقتة
            for img_file in image_files:
                try:
                    os.remove(img_file)
                    logger.info(f"🗑️ تم حذف: {img_file}")
                except Exception as e:
                    log_warning(f"❌ فشل حذف الصورة: {e}", module="handlers/download.py")
            
            return
        
        # إذا كان فيديو عادي - الكود القديم
        loop = asyncio.get_event_loop()

        # تتبع الأخطاء المتقدم - معرفة الصيغة المستخدمة
        format_used = ydl_opts.get('format', 'auto')
        is_pinterest = 'pinterest.com' in url or 'pin.it' in url
        logger.info(f"🎬 بدء التحميل - الرابط: {url[:50]}...")
        logger.info(f"📊 الصيغة المستخدمة: {format_used}")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # تحميل الملف
                await loop.run_in_executor(None, lambda: ydl.download([url]))
        except DownloadError as e:
            error_msg = str(e).lower()

            # تتبع الأخطاء المتقدم - تسجيل تفاصيل الخطأ
            logger.error(f"❌ خطأ في التحميل: {error_msg[:200]}")
            logger.error(f"📊 الصيغة التي تم استخدامها: {format_used}")

            # خطأ format غير متاح - محاولة مرة أخرى بدون format
            if "requested format is not available" in error_msg or "format" in error_msg:
                logger.warning("⚠️ خطأ format - محاولة التحميل بدون تحديد format")

                # إزالة format والمحاولة مرة أخرى
                if 'format' in ydl_opts:
                    del ydl_opts['format']
                    logger.info("🔄 إعادة المحاولة بالاختيار التلقائي...")

                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            await loop.run_in_executor(None, lambda: ydl.download([url]))
                        logger.info("✅ نجحت المحاولة الثانية بالاختيار التلقائي!")
                    except Exception as retry_error:
                        logger.error(f"❌ فشلت المحاولة الثانية أيضاً: {str(retry_error)[:200]}")
                        raise
                else:
                    raise
            # التعامل مع أخطاء تسجيل الدخول للمحتوى الخاص
            elif "log in" in error_msg or "login" in error_msg or "private" in error_msg or "members only" in error_msg:
                await processing_message.edit_text(
                    "❌ **لا يمكن تحميل هذا المحتوى**\n"
                    "Cannot download this content\n\n"
                    "🔒 هذا المحتوى خاص أو يتطلب تسجيل دخول\n"
                    "This content is private or requires login\n\n"
                    "💡 يمكنك إضافة ملف cookies.txt لتحميل المحتوى الخاص\n"
                    "You can add cookies.txt file to download private content"
                )
                return
            else:
                # خطأ آخر - إظهاره
                raise

        # معالجة المسارات بعد التحميل الناجح
        original_filepath = ydl.prepare_filename(info_dict)
        title = info_dict.get('title', 'video')
        cleaned_title = clean_filename(title)

        ext = 'mp3' if is_audio else 'mp4'
        new_filepath = os.path.join(VIDEO_PATH, f"{cleaned_title}.{ext}")

        if os.path.exists(original_filepath):
            if os.path.exists(new_filepath) and original_filepath != new_filepath:
                os.remove(new_filepath)
            os.rename(original_filepath, new_filepath)

        if not os.path.exists(new_filepath):
            raise FileNotFoundError(f"الملف غير موجود: {new_filepath}")
        
        logger.info(f"✅ تم التحميل: {new_filepath}")
        
        # التحقق من حالة اللوجو والفئة المستهدفة
        from database import is_logo_enabled, get_logo_target
        logo_enabled = is_logo_enabled()
        target_group, _ = get_logo_target()
        
        logo_path = config.get("LOGO_PATH")
        final_video_path = new_filepath
        
        # التحقق من رصيد نقاط بدون لوجو
        no_logo_credits = get_no_logo_credits(user_id)
        
        # تحديد نوع المستخدم
        is_regular_user = not is_subscribed_user and not is_user_admin  # عادي
        is_vip_user = is_subscribed_user and not is_user_admin  # VIP
        is_admin_user = is_user_admin  # Admin
        has_credits = no_logo_credits > 0  # لديه رصيد
        
        # منطق تحديد ما إذا كان المستخدم ضمن الفئة المستهدفة
        is_target_user = False
        
        # ملاحظة: "مع النقاط" = لا نهتم بالنقاط، "بدون النقاط" = يجب ألا يكون لديه نقاط
        if target_group == 'free_with_points':
            # العاديون (لا نهتم بالنقاط) - كل العاديين
            is_target_user = is_regular_user
        elif target_group == 'free_no_points':
            # العاديون (بدون نقاط) - العاديون الذين ليس لديهم نقاط
            is_target_user = is_regular_user and not has_credits
        elif target_group == 'free_all':
            # جميع العاديون
            is_target_user = is_regular_user
        elif target_group == 'vip_with_points':
            # VIP (لا نهتم بالنقاط) - كل VIP
            is_target_user = is_vip_user
        elif target_group == 'vip_no_points':
            # VIP (بدون نقاط) - VIP الذين ليس لديهم نقاط
            is_target_user = is_vip_user and not has_credits
        elif target_group == 'vip_all':
            # جميع VIP
            is_target_user = is_vip_user
        elif target_group == 'everyone_with_points':
            # الجميع (لا نهتم بالنقاط) - كل الناس ماعدا Admin
            is_target_user = not is_admin_user
        elif target_group == 'everyone_no_points':
            # الجميع (بدون نقاط) - الجميع الذين ليس لديهم نقاط
            is_target_user = (is_regular_user or is_vip_user) and not has_credits
        elif target_group == 'everyone_all':
            # الجميع
            is_target_user = not is_admin_user
        elif target_group == 'no_credits_only':
            # المستخدمون بدون نقاط فقط (عادي + VIP بدون نقاط)
            is_target_user = (is_regular_user or is_vip_user) and not has_credits
        elif target_group == 'everyone_except_no_credits':
            # الجميع عدا من لديهم نقاط (أي: ضع اللوجو للجميع إلا من لديه نقاط)
            is_target_user = (is_regular_user or is_vip_user) and not has_credits
        
        should_apply_logo = (
            not is_audio and 
            logo_enabled and 
            is_target_user and
            logo_path and 
            os.path.exists(logo_path)
        )
        
        # إضافة رسائل تشخيص
        logger.info(f"🔍 تشخيص اللوجو:")
        logger.info(f"  - is_audio: {is_audio}")
        logger.info(f"  - logo_enabled: {logo_enabled}")
        logger.info(f"  - target_group: {target_group}")
        logger.info(f"  - is_regular_user: {is_regular_user}")
        logger.info(f"  - is_vip_user: {is_vip_user}")
        logger.info(f"  - is_admin_user: {is_admin_user}")
        logger.info(f"  - has_credits: {has_credits}")
        logger.info(f"  - is_target_user: {is_target_user}")
        logger.info(f"  - logo_path: {logo_path}")
        logger.info(f"  - logo_exists: {os.path.exists(logo_path) if logo_path else False}")
        logger.info(f"  - should_apply_logo: {should_apply_logo}")
        
        if not should_apply_logo:
            if not logo_enabled:
                log_warning("⚠️ اللوجو معطل من الإعدادات", module="handlers/download.py")
            elif is_audio:
                log_warning("⚠️ الملف صوتي، لا يطبق لوجو", module="handlers/download.py")
            elif not is_target_user:
                log_warning(f"⚠️ المستخدم ليس ضمن الفئة المستهدفة: {target_group}", module="handlers/download.py")
            elif not logo_path:
                log_warning("⚠️ مسار اللوجو غير معرف", module="handlers/download.py")
            elif not os.path.exists(logo_path):
                log_warning(f"⚠️ ملف اللوجو غير موجود: {logo_path}", module="handlers/download.py")
        
        if should_apply_logo:
            logger.info(f"✅ سيتم تطبيق اللوجو على الفيديو")
        
        if should_apply_logo:
            from utils import apply_animated_watermark

            temp_watermarked_path = new_filepath.replace(f".{ext}", f"_watermarked.{ext}")

            # تتبع حالة الملف قبل تطبيق اللوجو
            logger.info(f"🔍 [TRACE] قبل تطبيق اللوجو:")
            logger.info(f"  - new_filepath: {new_filepath}")
            logger.info(f"  - exists: {os.path.exists(new_filepath)}")
            if os.path.exists(new_filepath):
                logger.info(f"  - size: {os.path.getsize(new_filepath) / 1024 / 1024:.2f}MB")
            logger.info(f"  - temp_watermarked_path: {temp_watermarked_path}")
            logger.info(f"  - logo_path: {logo_path}")

            # استخدام ThreadPoolExecutor لتجنب التجميد أثناء FFmpeg
            loop = asyncio.get_event_loop()
            result_path = await loop.run_in_executor(
                executor,
                apply_animated_watermark,
                new_filepath,
                temp_watermarked_path,
                logo_path
            )

            # تتبع حالة الملف بعد تطبيق اللوجو
            logger.info(f"🔍 [TRACE] بعد تطبيق اللوجو:")
            logger.info(f"  - result_path: {result_path}")
            logger.info(f"  - new_filepath exists: {os.path.exists(new_filepath)}")
            logger.info(f"  - result_path exists: {os.path.exists(result_path)}")
            logger.info(f"  - temp_watermarked_path exists: {os.path.exists(temp_watermarked_path)}")

            if result_path != new_filepath and os.path.exists(result_path):
                final_video_path = result_path
                logger.info(f"✨ تم تطبيق اللوجو المتحرك")
            else:
                # فشل اللوجو، استخدم الملف الأصلي
                logger.warning(f"⚠️ فشل تطبيق اللوجو، سيتم استخدام الملف الأصلي")
                final_video_path = new_filepath
        elif has_credits and not is_subscribed_user and not is_user_admin:
            # المستخدم لديه نقاط ولم يتم وضع اللوجو، فنستهلك نقطة
            if use_no_logo_credit(user_id):
                logger.info(f"✅ تم استخدام نقطة بدون لوجو للمستخدم {user_id}، المتبقي: {no_logo_credits - 1}")
                # إرسال إشعار للمستخدم
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🎨 تم استخدام نقطة بدون لوجو!\n💰 الرصيد المتبقي: {no_logo_credits - 1} فيديو"
                )

        # Safety check: ensure final_video_path is never None and points to existing file
        if final_video_path is None:
            final_video_path = new_filepath
            logger.warning(f"⚠️ final_video_path was None, using new_filepath: {new_filepath}")

        # التحقق النهائي من وجود الملف
        logger.info(f"🔍 [TRACE] قبل الرفع:")
        logger.info(f"  - final_video_path: {final_video_path}")
        logger.info(f"  - exists: {os.path.exists(final_video_path)}")

        if not os.path.exists(final_video_path):
            # محاولة البحث عن الملف الأصلي
            logger.error(f"❌ final_video_path غير موجود: {final_video_path}")
            if os.path.exists(new_filepath):
                logger.info(f"✅ تم العثور على new_filepath، استخدامه بدلاً منه")
                final_video_path = new_filepath
            else:
                raise FileNotFoundError(f"لم يتم العثور على الملف: {final_video_path} أو {new_filepath}")

        file_size = os.path.getsize(final_video_path)
        total_mb = file_size / (1024 * 1024)

        await safe_edit_message(
            processing_message,
            f"📤 جاري الرفع...\n\n"
            f"⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%\n\n"
            f"📦 الحجم: {total_mb:.1f} MB"
        )
        
        if file_size > 2 * 1024 * 1024 * 1024:
            await safe_edit_message(processing_message, "❌ الملف كبير جداً! (أكثر من 2GB)")
            return
        
        duration = info_dict.get('duration', 0)
        uploader = info_dict.get('uploader', 'Unknown')[:40]
        
        caption_text = (
            f"🎬 {title[:50]}\n\n"
            f"👤 {uploader}\n"
            f"⏱️ {format_duration(duration)} | 📦 {format_file_size(file_size)}\n"
            f"{'🎵' if is_audio else '🎥'} {'💎 VIP' if is_subscribed_user else '🆓 مجاني'}\n\n"
            f"✨ بواسطة @{context.bot.username}"
        )

        # محاولة إرسال الملف مع إعادة المحاولة في حالة TimedOut
        sent_message, upload_error = await send_file_with_retry(
            context=context,
            chat_id=update.effective_chat.id,
            file_path=final_video_path,
            is_audio=is_audio,
            caption=caption_text,
            reply_to_message_id=update.effective_message.message_id,
            duration=duration,
            info_dict=info_dict,
            max_retries=3,
            progress_message=processing_message  # إضافة progress tracking للرفع
        )

        if sent_message:
            # نجح الرفع
            if is_audio:
                logger.info(f"✅ تم تحميل الصوت بنجاح — {user_id} — {title[:30]} — {format_duration(duration)}")
            else:
                logger.info(f"✅ تم تحميل الفيديو بنجاح — {user_id} — {title[:30]} — {format_duration(duration)}")
            logger.info(f"✅ تم الإرسال بنجاح")

        else:
            # فشل الرفع بعد جميع المحاولات - استخدام البديل
            logger.error(f"❌ فشل رفع الملف بعد {3} محاولات: {upload_error}")

            # محاولة رفع الملف إلى سيرفر خارجي (placeholder)
            alternative_url = await upload_to_server(final_video_path, user_id)

            # الحصول على حجم الملف بأمان (قد يكون محذوفاً)
            file_size_str = "Unknown"
            if os.path.exists(final_video_path):
                try:
                    file_size_str = format_file_size(os.path.getsize(final_video_path))
                except:
                    pass

            # إرسال رسالة للمستخدم مع رابط بديل
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        f"⚠️ عذراً، الملف كبير جداً للرفع مباشرة!\n\n"
                        f"📊 الحجم: {file_size_str}\n"
                        f"⏱️ المدة: {format_duration(duration)}\n\n"
                        f"💡 نعمل على حل هذه المشكلة قريباً.\n"
                        f"الرجاء المحاولة مع فيديو أقصر أو جودة أقل."
                    ),
                    reply_to_message_id=update.effective_message.message_id,
                )
                logger.info(f"✅ [perform_download] تم إرسال رسالة خطأ الحجم للمستخدم {user_id}")
            except Exception as msg_error:
                import traceback
                logger.error(f"❌ [perform_download] فشل إرسال رسالة الخطأ: {type(msg_error).__name__}: {str(msg_error)}")
                logger.error(f"📍 [perform_download] Stack trace:\n{traceback.format_exc()}")

            # إرسال تقرير فشل إلى قناة السجلات مع معلومات كاملة
            if LOG_CHANNEL_ID:
                try:
                    log_channel_id = int(LOG_CHANNEL_ID)

                    # تحضير معلومات العضو
                    user_name = user.full_name
                    username_display = f"@{user.username}" if user.username else "لا يوجد"

                    fail_report_text = (
                        "🔴 <b>فشل رفع ملف كبير (TimedOut)</b>\n"
                        f"{'━' * 30}\n\n"
                        f"👤 <b>معلومات العضو:</b>\n"
                        f"   • الاسم: {user_name}\n"
                        f"   • اليوزر: {username_display}\n"
                        f"   • ID: <code>{user_id}</code>\n\n"
                        f"📝 <b>تفاصيل الملف:</b>\n"
                        f"   • العنوان: {title[:100]}\n"
                        f"   • الحجم: {file_size_str}\n"
                        f"   • المدة: {format_duration(duration)}\n\n"
                        f"🔗 <b>الرابط الأصلي:</b>\n{url[:150]}\n\n"
                        f"⚠️ <b>سبب الفشل:</b> {upload_error}\n\n"
                        f"🔗 <b>الرابط البديل:</b>\n{alternative_url}\n\n"
                        f"📅 <b>الوقت:</b> {datetime.now().strftime('%d-%m-%Y — %H:%M UTC')}\n"
                        f"{'━' * 30}"
                    )
                    await context.bot.send_message(
                        chat_id=log_channel_id,
                        text=fail_report_text,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    logger.info("✅ تم إرسال تقرير الفشل إلى قناة السجلات")
                except Exception as e:
                    logger.error(f"❌ فشل إرسال تقرير الفشل: {e}")

            # لا نرمي استثناء هنا لأننا قدمنا حل بديل
            # بدلاً من ذلك، نكمل التنفيذ العادي لكن بدون sent_message
            sent_message = None

        try:
            await processing_message.delete()
        except Exception as e:
            logger.debug(f"فشل حذف رسالة المعالجة: {e}")
        
        if not is_user_admin and not is_subscribed_user:
            from database import get_daily_download_limit_setting
            increment_download_count(user_id)
            daily_limit = get_daily_download_limit_setting()
            remaining = daily_limit - get_daily_download_count(user_id)
            if remaining > 0:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"ℹ️ تبقى لك {remaining} تحميلات مجانية اليوم"
                )

        # إرسال سجل للقناة فقط إذا نجح الرفع
        if sent_message:
            await send_log_to_channel(context, update, user, info_dict, final_video_path, sent_message, is_audio)
        
        # تسجيل الإحصائيات - تحميل ناجح
        from database import record_download_attempt
        speed_mbps = 0  # يمكن حسابها من بيانات التقدم
        record_download_attempt(success=True, speed=speed_mbps)
        
    except Exception as e:
        logger.error(f"❌ خطأ: {e}", exc_info=True)

        # تحديد نوع الخطأ
        error_type = type(e).__name__
        error_message = str(e)

        # تسجيل خطأ التحميل محلياً (ليس خطأ جسيم)
        error_details = f"فشل تحميل فيديو للمستخدم {user_id}\nالرابط: {url}\nالخطأ: {error_message}"
        log_warning(error_details, module="handlers/download.py")

        # تسجيل الإحصائيات - تحميل فاشل
        from database import record_download_attempt
        record_download_attempt(success=False, speed=0)

        # === نظام البلاغات التلقائي ===
        # 1. إنشاء بلاغ في قاعدة البيانات
        from database import create_error_report

        username = user.username if user.username else user.full_name
        report_id = create_error_report(
            user_id=user_id,
            username=username,
            url=url,
            error_type=error_type,
            error_message=error_message[:500]  # حد 500 حرف
        )

        # 2. إرسال تقرير إلى قناة السجلات مع تفاصيل المنصة
        platform_name = "Unknown"
        if 'tiktok.com' in url:
            platform_name = "TikTok"
        elif 'instagram.com' in url:
            platform_name = "Instagram"
        elif 'facebook.com' in url or 'fb.watch' in url or 'fb.com' in url:
            platform_name = "Facebook"
        elif 'youtube.com' in url or 'youtu.be' in url:
            platform_name = "YouTube"
        elif 'twitter.com' in url or 'x.com' in url:
            platform_name = "Twitter/X"
        elif 'pinterest.com' in url or 'pin.it' in url:
            platform_name = "Pinterest"
        elif 'reddit.com' in url or 'redd.it' in url:
            platform_name = "Reddit"
        elif 'vimeo.com' in url:
            platform_name = "Vimeo"
        elif 'dailymotion.com' in url or 'dai.ly' in url:
            platform_name = "Dailymotion"
        elif 'twitch.tv' in url:
            platform_name = "Twitch"

        if LOG_CHANNEL_ID:
            try:
                log_channel_id = int(LOG_CHANNEL_ID)

                # تحضير معلومات العضو الكاملة
                user_name = user.full_name
                username_display = f"@{user.username}" if user.username else "لا يوجد"

                error_report_text = (
                    f"⚠️ <b>فشل تحميل من {platform_name}</b>\n"
                    f"{'━' * 30}\n\n"
                    f"👤 <b>معلومات العضو:</b>\n"
                    f"   • الاسم: {user_name}\n"
                    f"   • اليوزر: {username_display}\n"
                    f"   • ID: <code>{user_id}</code>\n\n"
                    f"📱 <b>المنصة:</b> {platform_name}\n\n"
                    f"🔗 <b>الرابط:</b>\n{url[:150]}\n\n"
                    f"⚠️ <b>نوع الخطأ:</b> <code>{error_type}</code>\n\n"
                    f"💬 <b>تفاصيل الخطأ:</b>\n<code>{error_message[:300]}</code>\n\n"
                    f"📅 <b>الوقت:</b> {datetime.now().strftime('%d-%m-%Y — %H:%M UTC')}\n"
                    f"{'━' * 30}"
                )

                await context.bot.send_message(
                    chat_id=log_channel_id,
                    text=error_report_text,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )

                logger.info(f"✅ تم إرسال تقرير الخطأ لقناة السجلات")
            except Exception as log_error:
                log_warning(f"❌ فشل إرسال تقرير الخطأ لقناة السجلات: {log_error}", module="handlers/download.py")

        # 3. إشعار المستخدم بالفشل مع رسالة مخصصة حسب المنصة
        error_text = "❌ **حدث خطأ أثناء تحميل المقطع!**\n\n"

        # رسائل مخصصة حسب نوع الخطأ والمنصة
        if "login" in error_message.lower() or "sign in" in error_message.lower() or "comfortable" in error_message.lower():
            # TikTok/Instagram يطلب تسجيل دخول
            if 'tiktok.com' in url:
                error_text += (
                    "🔐 **هذا المقطع من TikTok يتطلب تسجيل دخول**\n\n"
                    "💡 الحلول المتاحة:\n"
                    "• جرب رابط مقطع آخر عام\n"
                    "• أو انسخ الرابط من المتصفح مباشرة\n\n"
                )
            elif 'instagram.com' in url:
                error_text += (
                    "🔐 **هذا المقطع من Instagram قد يكون خاصاً**\n\n"
                    "💡 جرب رابط مقطع عام آخر\n\n"
                )
        elif "csrf" in error_message.lower() or "token" in error_message.lower():
            # مشكلة csrf token في Instagram
            error_text += (
                "🔄 **مشكلة مؤقتة في الاتصال بـ Instagram**\n\n"
                "💡 جرب الرابط مرة أخرى بعد قليل\n\n"
            )
        elif "unavailable" in error_message.lower() or "private" in error_message.lower():
            # فيديو غير متاح أو خاص
            error_text += (
                "🔒 **المقطع غير متاح أو خاص**\n\n"
                "💡 تأكد أن الرابط صحيح ومتاح للعامة\n\n"
            )
        elif "nsig" in error_message.lower():
            # مشكلة YouTube nsig
            error_text += (
                "⚠️ **مشكلة مؤقتة في فك تشفير YouTube**\n\n"
                "💡 جرب مرة أخرى خلال دقائق\n\n"
            )
        else:
            # رسالة عامة
            error_text += (
                "📩 تم إرسال مشكلتك إلى المدير\n"
                "🔔 سيتم إعلامك عند التصليح\n\n"
            )

        error_text += "شكراً لصبرك! 💚"

        # محاولة تحديث الرسالة مع retry mechanism
        success = await safe_edit_message(processing_message, error_text, parse_mode='Markdown')

        # إذا فشل التحديث، إرسال رسالة جديدة
        if not success:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=error_text,
                    parse_mode='Markdown'
                )
            except Exception as send_error:
                log_warning(f"فشل إرسال رسالة الخطأ: {send_error}", module="handlers/download.py")
    
    finally:
        for filepath in [new_filepath, temp_watermarked_path]:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"🗑️ تم حذف: {filepath}")
                except Exception as e:
                    logger.error(f"❌ فشل الحذف: {e}")

@rate_limit(seconds=10)
async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج تحميل الفيديوهات - يدعم جميع المنصات"""
    user = update.message.from_user
    user_id = user.id
    url = update.message.text.strip()

    # استخدام الذاكرة المؤقتة للحصول على لغة المستخدم
    lang = get_cached_user_data(user_id, get_user_language)

    # رد سريع للمستخدم - تحسين الإحساس بالاستجابة
    processing_msg = await update.message.reply_text("⏳ جاري المعالجة...")

    # جلب بيانات المستخدم مع التخزين المؤقت
    user_data = get_cached_user_data(user_id, get_user)

    # التحقق من بيانات المستخدم
    if not user_data:
        await processing_msg.edit_text("❌ لم يتم العثور على بياناتك. الرجاء إرسال /start")
        return

    # التحقق من صحة الرابط
    if not validate_url(url):
        error_msg = get_message(lang, 'invalid_url') if lang else "❌ الرابط غير صحيح. الرجاء إرسال رابط فيديو صحيح."
        await processing_msg.edit_text(error_msg)
        log_warning(f"رابط غير صحيح من المستخدم {user_id}: {url}", module="handlers/download.py")
        return

    # حذف رسالة المعالجة المبدئية
    try:
        await processing_msg.delete()
    except Exception:
        pass

    is_user_admin = is_admin(user_id)
    is_subscribed_user = is_subscribed(user_id)
    config = get_config()
    
    # التحقق من المنصة المسموحة
    from database import is_platform_allowed
    platform = get_platform_from_url(url)
    
    # ⭐ إذا كانت المنصة "unknown"، نسمح بالمحاولة لأن yt-dlp يدعم 1000+ موقع
    if platform != 'unknown' and not is_platform_allowed(platform):
        platform_names = {
            'youtube': 'YouTube',
            'facebook': 'Facebook', 
            'instagram': 'Instagram',
            'tiktok': 'TikTok',
            'pinterest': 'Pinterest',
            'twitter': 'Twitter/X',
            'reddit': 'Reddit',
            'vimeo': 'Vimeo',
            'dailymotion': 'Dailymotion',
            'twitch': 'Twitch'
        }
        platform_name = platform_names.get(platform, platform)
        
        await update.message.reply_text(
            f"🚫 منصة {platform_name} معطلة حالياً!\n\n"
            f"يرجى التواصل مع المدير لتفعيلها."
        )
        return
    
    if is_adult_content(url):
        await update.message.reply_text("🚫 محتوى محظور! هذا الموقع محظور.")
        return

    # التحقق من الحد اليومي (فقط إذا كان الاشتراك مفعلاً)
    from database import is_subscription_enabled, get_daily_download_limit_setting
    subscription_enabled = is_subscription_enabled()

    if subscription_enabled and not is_user_admin and not is_subscribed_user:
        daily_count = get_daily_download_count(user_id)
        daily_limit = get_daily_download_limit_setting()  # جلب الحد من قاعدة البيانات
        if daily_count >= daily_limit:
            keyboard = [[InlineKeyboardButton(
                "⭐ اشترك الآن",
                url="https://instagram.com/7kmmy"
            )]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"🚫 وصلت للحد اليومي ({daily_limit} تحميلات). اشترك للتحميل بلا حدود!",
                reply_markup=reply_markup
            )
            return
    # إذا كان الاشتراك معطلاً، السماح بالتحميل بدون قيود
    
    processing_message = await update.message.reply_text("🔍 جاري التحليل...")

    try:
        # إعدادات التحليل
        ydl_opts = get_ydl_opts_for_platform(url)
        ydl_opts['skip_download'] = True  # فقط للتحليل

        # إزالة format في مرحلة التحليل لتجنب مشاكل التوافق
        # سنحدد format فقط عند التحميل الفعلي
        if 'format' in ydl_opts:
            del ydl_opts['format']

        loop = asyncio.get_event_loop()

        # 📊 Logging محسّن لتتبع الأخطاء
        platform = get_platform_from_url(url)
        is_story = '/stories/' in url.lower() or '/story/' in url.lower()

        if is_story:
            logger.info(f"🔍 [STORY_DEBUG] Platform: {platform}, URL: {url[:80]}...")
            logger.info(f"🔍 [STORY_DEBUG] Cookies loaded: {ydl_opts.get('cookiefile') is not None}")
            logger.info(f"🔍 [STORY_DEBUG] YDL opts keys: {list(ydl_opts.keys())}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if is_story:
                logger.info(f"🔍 [STORY_DEBUG] Attempting extract_info for {platform} story...")

            info_dict = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

            if is_story:
                logger.info(f"✅ [STORY_DEBUG] Successfully extracted! Extractor: {info_dict.get('extractor', 'unknown')}")
        
        title = info_dict.get('title', 'فيديو')
        duration = info_dict.get('duration', 0)
        
        if is_adult_content(url, title):
            await processing_message.edit_text("🚫 محتوى محظور!")
            return

        # التحقق من القيود الزمنية (فقط إذا كان الاشتراك مفعلاً)
        from database import is_subscription_enabled, get_free_time_limit
        subscription_enabled = is_subscription_enabled()

        if subscription_enabled:
            # الاشتراك مفعل - تطبيق القيود على غير المشتركين
            free_time_limit = get_free_time_limit()  # جلب الحد من قاعدة البيانات (بالدقائق)
            max_free_duration = free_time_limit * 60  # تحويل إلى ثواني
            if not is_user_admin and not is_subscribed_user and duration and duration > max_free_duration:
                # Track rejection for server load monitoring (V5.0.1)
                duration_minutes = duration / 60
                await track_limit_rejection(context, user_id, duration_minutes, free_time_limit, url)

                # Show enhanced message to user
                limit_text = "♾️ غير محدود" if free_time_limit == -1 else f"{free_time_limit} دقيقة"

                keyboard = [[InlineKeyboardButton(
                    "⭐ اشترك الآن",
                    url="https://instagram.com/7kmmy"
                )]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await processing_message.edit_text(
                    f"⚠️ **عذراً، لا يمكنك تحميل مقاطع تتجاوز {limit_text}**\n\n"
                    f"🎬 مدة الفيديو: {duration_minutes:.1f} دقيقة\n"
                    f"⏱️ الحد المسموح: {limit_text}\n\n"
                    f"🖥️ **السبب:** السيرفر لا يتحمل ملفات بهذا الطول\n\n"
                    f"💡 **الحل:** اشترك للوصول إلى تحميل غير محدود ♾️",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return
        # إذا كان الاشتراك معطلاً، السماح بالتحميل بدون قيود
        
        await processing_message.delete()
        
        await show_quality_menu(update, context, url, info_dict)
        
    except Exception as e:
        logger.error(f"❌ خطأ في التحليل: {e}", exc_info=True)
        error_msg = str(e)

        # 🔴 تتبع الخطأ بنظام متقدم
        platform = get_platform_from_url(url)
        ErrorTracker.track_download_error(
            platform=platform,
            url=url,
            error_message=error_msg,
            user_id=user_id,
            cookies_used=platform_cookies is not None if 'platform_cookies' in locals() else False,
            extractor_used="unknown"
        )

        # 📢 إرسال الخطأ لقناة السجلات (NEW: Channel Error Tracking)
        try:
            from handlers.channel_manager import channel_manager
            await channel_manager.log_error(
                bot=context.bot,
                error_type=f"Download Error - {platform.title()}",
                error_message=f"{error_msg[:200]}",  # أول 200 حرف فقط
                user_id=user_id
            )
        except Exception as log_error:
            logger.error(f"❌ فشل إرسال الخطأ للقناة: {log_error}")

        # 💾 حفظ البلاغ في قاعدة البيانات (لوحة الأدمن)
        try:
            from database import create_error_report
            # الحصول على username
            username = user.username if hasattr(user, 'username') else None
            if not username:
                username = f"user_{user_id}"

            create_error_report(
                user_id=user_id,
                username=username,
                url=url,
                error_type=f"Download Error - {platform.title()}",
                error_message=error_msg[:500]  # حفظ أول 500 حرف
            )
            logger.info(f"✅ تم حفظ البلاغ في قاعدة البيانات للمستخدم {user_id}")
        except Exception as db_error:
            logger.error(f"❌ فشل حفظ البلاغ في قاعدة البيانات: {db_error}")

        # ⭐ معالج خاص لأخطاء cookies database
        if 'could not find' in error_msg.lower() and 'cookies database' in error_msg.lower():
            platform = get_platform_from_url(url)
            platform_name = {
                'tiktok': 'TikTok',
                'instagram': 'Instagram',
                'facebook': 'Facebook',
                'twitter': 'Twitter/X',
                'pinterest': 'Pinterest'
            }.get(platform, platform.title())

            await processing_message.edit_text(
                f"❌ **فشل تحميل الفيديو من {platform_name}!**\n\n"
                f"🔐 **السبب:** لا يمكن العثور على cookies من المتصفح\n\n"
                f"💡 **الحل:**\n\n"
                f"1️⃣ **ارفع ملف cookies يدوياً:**\n"
                f"   • سجل دخول {platform_name} في المتصفح\n"
                f"   • استخدم إضافة 'Get cookies.txt LOCALLY'\n"
                f"   • احفظ الملف وارفعه للبوت\n\n"
                f"2️⃣ **رفع الكوكيز للبوت:**\n"
                f"   /admin → إدارة الكوكيز → {platform_name}\n\n"
                f"📝 **ملاحظة:** البوت يعمل على خادم بدون متصفح،\n"
                f"لذلك يحتاج ملف cookies يدوي للمنصات المحمية.",
                parse_mode='Markdown'
            )
            return

        # ⭐ معالج خاص لأخطاء TikTok
        if 'tiktok' in error_msg.lower() or 'tiktok' in url.lower():
            if 'video not available' in error_msg.lower() or 'status code 0' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من TikTok!**\n\n"
                    "🎵 **الأسباب المحتملة:**\n\n"
                    "1️⃣ **الفيديو محذوف أو خاص**\n"
                    "   • تأكد أن الفيديو لا يزال موجوداً\n"
                    "   • تحقق أن الحساب ليس خاصاً\n\n"
                    "2️⃣ **الفيديو محظور جغرافياً**\n"
                    "   • قد يكون غير متاح في منطقتك\n\n"
                    "3️⃣ **مشكلة في الكوكيز**\n"
                    "   • الكوكيز قد تحتاج إلى تحديث\n\n"
                    "💡 **الحلول:**\n\n"
                    "• افتح الرابط في TikTok وتأكد أنه يعمل\n"
                    "• جرب فيديو آخر من TikTok\n"
                    "• إذا استمرت المشكلة، جدّد الكوكيز:\n"
                    "  /admin → إدارة الكوكيز → TikTok\n\n"
                    "⚠️ **ملاحظة:** TikTok يصعّب التحميل بشكل مستمر\n"
                    "بعض الفيديوهات قد لا تكون قابلة للتحميل حالياً",
                    parse_mode='Markdown'
                )
                return

        # ⭐ معالج خاص لأخطاء Instagram (Reels/Posts/Stories)
        if 'instagram' in error_msg.lower() or 'instagram.com' in url.lower():
            # معالجة خطأ "empty media response" - المشكلة الأكثر شيوعاً
            if 'empty media response' in error_msg.lower() or 'not granting access' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل المحتوى من Instagram!**\n\n"
                    "🔐 **السبب:** Instagram يحتاج كوكيز صالحة\n\n"
                    "💡 **الحلول:**\n\n"
                    "1️⃣ **جدّد الكوكيز:**\n"
                    "   • سجل دخول Instagram في المتصفح (Chrome أو Firefox)\n"
                    "   • استخدم إضافة 'Get cookies.txt LOCALLY'\n"
                    "   • احفظ ملف الكوكيز وارفعه للبوت\n\n"
                    "2️⃣ **رفع الكوكيز للبوت:**\n"
                    "   • أرسل الأمر: /admin\n"
                    "   • اختر: إدارة الكوكيز\n"
                    "   • اختر: Instagram\n"
                    "   • ارفع ملف cookies.txt\n\n"
                    "3️⃣ **تحقق من المحتوى:**\n"
                    "   • افتح الرابط في المتصفح\n"
                    "   • تأكد أن المحتوى موجود وليس خاص\n"
                    "   • الستوريات تختفي بعد 24 ساعة!\n\n"
                    "📝 **ملاحظة:** الكوكيز يجب أن تكون:\n"
                    "   ✓ حديثة (أقل من أسبوع)\n"
                    "   ✓ من حساب Instagram مسجل دخول\n"
                    "   ✓ تحتوي على sessionid و ds_user_id\n\n"
                    "⚠️ بعد رفع الكوكيز، انتظر 10 ثواني ثم جرب مرة أخرى!",
                    parse_mode='Markdown'
                )
                return

            # معالجة خاصة للـ Stories
            elif 'instagram:story' in error_msg.lower() or 'stories' in url.lower():
                if 'unreachable' in error_msg.lower() or 'login' in error_msg.lower() or 'cookies' in error_msg.lower():
                    await processing_message.edit_text(
                        "❌ **فشل تحميل الستوري من Instagram!**\n\n"
                        "🔐 **السبب:** الستوري يحتاج كوكيز صالحة\n\n"
                        "💡 **الحلول:**\n\n"
                        "1️⃣ **جدّد الكوكيز:**\n"
                        "   • سجل دخول Instagram في المتصفح\n"
                        "   • استخدم إضافة 'Get cookies.txt LOCALLY'\n"
                        "   • احفظ الملف وارفعه للبوت\n\n"
                        "2️⃣ **تأكد من الكوكيز:**\n"
                        "   • يجب أن تكون حديثة (أقل من أسبوع)\n"
                        "   • من حساب مسجل دخول بالفعل\n"
                        "   • تحتوي sessionid و ds_user_id\n\n"
                        "3️⃣ **تحقق من الستوري:**\n"
                        "   • الستوريات تختفي بعد 24 ساعة!\n"
                        "   • تأكد أنه لا يزال موجوداً\n\n"
                        "📝 **رفع الكوكيز:**\n"
                        "/admin → إدارة الكوكيز → Instagram\n\n"
                        "⚠️ إذا جددت الكوكيز الآن، جرب مرة أخرى بعد 10 ثواني!",
                        parse_mode='Markdown'
                    )
                    return

        # ⭐ معالج خاص لأخطاء Pinterest
        if 'pinterest' in error_msg.lower() or 'pinterest.com' in url.lower() or 'pin.it' in url.lower():
            if 'no video formats found' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Pinterest!**\n\n"
                    "📌 **السبب:** هذا الرابط لا يحتوي على فيديو\n\n"
                    "💡 **الحلول:**\n\n"
                    "1️⃣ **تأكد من نوع المحتوى:**\n"
                    "   • افتح الرابط في المتصفح\n"
                    "   • تحقق أنه فيديو وليس صورة\n\n"
                    "2️⃣ **استخدم الرابط الصحيح:**\n"
                    "   • انسخ الرابط من شريط العنوان مباشرة\n"
                    "   • تجنب روابط /sent/ أو /pin/\n\n"
                    "3️⃣ **جرب محتوى آخر:**\n"
                    "   • بعض محتوى Pinterest قد يكون محمياً\n"
                    "   • جرب pin عام آخر",
                    parse_mode='Markdown'
                )
            else:
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Pinterest!**\n\n"
                    "📌 **الأسباب المحتملة:**\n\n"
                    "1️⃣ **المحتوى محذوف أو خاص**\n"
                    "   • تأكد أن الفيديو لا يزال موجوداً\n"
                    "   • تحقق أن الحساب ليس خاصاً\n\n"
                    "2️⃣ **مشكلة في الرابط**\n"
                    "   • انسخ الرابط الأصلي من شريط العنوان\n"
                    "   • تجنب الروابط المختصرة /sent/\n\n"
                    "3️⃣ **مشكلة تقنية مؤقتة**\n"
                    "   • Pinterest يحدث خوادمه باستمرار\n\n"
                    "💡 **الحلول:**\n"
                    "• جرب فيديو آخر من Pinterest\n"
                    "• حاول مرة أخرى بعد دقائق\n"
                    "• تأكد من الرابط في المتصفح أولاً",
                    parse_mode='Markdown'
                )
            return

        # ⭐ معالج خاص لأخطاء Reddit
        if 'reddit' in error_msg.lower() or 'reddit.com' in url.lower() or 'redd.it' in url.lower():
            logger.error(f"❌ [Reddit] خطأ في التحميل: {error_msg[:200]}")
            if 'conflicting range' in error_msg.lower() or 'downloaded file is empty' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Reddit!**\n\n"
                    "🔴 **السبب:** مشكلة تقنية في خوادم Reddit\n\n"
                    "💡 **الحلول:**\n\n"
                    "1️⃣ **حاول مرة أخرى:**\n"
                    "   • أرسل الرابط مرة أخرى بعد ثواني\n"
                    "   • Reddit يعاني أحياناً من مشاكل مؤقتة\n\n"
                    "2️⃣ **جرب جودة أخرى:**\n"
                    "   • اختر 'متوسطة' بدلاً من 'عالية'\n"
                    "   • بعض الفيديوهات تعمل بجودة أقل\n\n"
                    "3️⃣ **استخدم رابط مباشر:**\n"
                    "   • افتح المنشور في المتصفح\n"
                    "   • انسخ رابط الفيديو مباشرة (v.redd.it)\n\n"
                    "⚠️ **ملاحظة:** Reddit يغيّر طريقة عرض الفيديوهات باستمرار،\n"
                    "بعض الفيديوهات قد لا تكون قابلة للتحميل حالياً",
                    parse_mode='Markdown'
                )
                return
            elif 'no video formats found' in error_msg.lower() or 'no media' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل المحتوى من Reddit!**\n\n"
                    "🔴 **السبب:** هذا المنشور لا يحتوي على فيديو\n\n"
                    "💡 **الحلول:**\n\n"
                    "1️⃣ **تأكد من نوع المنشور:**\n"
                    "   • بعض منشورات Reddit صور فقط\n"
                    "   • بعضها نصوص أو روابط خارجية\n\n"
                    "2️⃣ **جرب منشور آخر:**\n"
                    "   • ابحث عن منشورات تحتوي على v.redd.it\n"
                    "   • تأكد من وجود رمز ▶️ على المنشور\n\n"
                    "3️⃣ **استخدم الرابط المباشر:**\n"
                    "   • انسخ رابط الفيديو من المتصفح\n"
                    "   • تجنب روابط التعليقات فقط",
                    parse_mode='Markdown'
                )
            elif 'private' in error_msg.lower() or 'nsfw' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل المحتوى من Reddit!**\n\n"
                    "🔒 **السبب:** المحتوى خاص أو محظور (NSFW)\n\n"
                    "💡 **ملاحظة:**\n"
                    "• المحتوى NSFW قد يتطلب تسجيل دخول\n"
                    "• Subreddits الخاصة غير متاحة للتحميل\n"
                    "• جرب محتوى عام آخر من Reddit",
                    parse_mode='Markdown'
                )
            else:
                await processing_message.edit_text(
                    "❌ **فشل تحميل المحتوى من Reddit!**\n\n"
                    "🔴 **الأسباب المحتملة:**\n\n"
                    "1️⃣ **المنشور محذوف**\n"
                    "   • تأكد أن المنشور لا يزال موجوداً\n\n"
                    "2️⃣ **Subreddit خاص**\n"
                    "   • بعض المجتمعات خاصة أو محظورة\n\n"
                    "3️⃣ **المحتوى من موقع خارجي**\n"
                    "   • بعض المنشورات روابط لمواقع أخرى\n\n"
                    "💡 **الحلول:**\n"
                    "• تأكد أن الرابط يحتوي على v.redd.it\n"
                    "• جرب منشور عام آخر\n"
                    "• افتح الرابط في المتصفح للتأكد",
                    parse_mode='Markdown'
                )
            return

        # ⭐ معالج خاص لأخطاء Vimeo
        if 'vimeo' in error_msg.lower() or 'vimeo.com' in url.lower():
            logger.error(f"❌ [Vimeo] خطأ في التحميل: {error_msg[:200]}")
            if 'password' in error_msg.lower() or 'private' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Vimeo!**\n\n"
                    "🔒 **السبب:** الفيديو محمي بكلمة مرور أو خاص\n\n"
                    "💡 **ملاحظات:**\n\n"
                    "• Vimeo يسمح لأصحاب المحتوى بحماية فيديوهاتهم\n"
                    "• الفيديوهات الخاصة تحتاج رابط مباشر\n"
                    "• بعض الفيديوهات محدودة جغرافياً\n\n"
                    "🔓 **الحلول:**\n"
                    "• جرب فيديو عام آخر من Vimeo\n"
                    "• تأكد أن الفيديو يمكن مشاهدته بدون تسجيل دخول\n"
                    "• اطلب الرابط المباشر من صاحب الفيديو",
                    parse_mode='Markdown'
                )
            elif 'unavailable' in error_msg.lower() or 'not found' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Vimeo!**\n\n"
                    "🔴 **السبب:** الفيديو غير متاح أو محذوف\n\n"
                    "💡 **الحلول:**\n"
                    "• تأكد من الرابط في المتصفح أولاً\n"
                    "• الفيديو قد يكون محذوفاً من Vimeo\n"
                    "• جرب فيديو آخر متاح",
                    parse_mode='Markdown'
                )
            else:
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Vimeo!**\n\n"
                    "🔴 **الأسباب المحتملة:**\n\n"
                    "1️⃣ **قيود على التحميل**\n"
                    "   • بعض الفيديوهات محمية من التحميل\n\n"
                    "2️⃣ **محتوى مدفوع أو خاص**\n"
                    "   • Vimeo لديه محتوى premium\n\n"
                    "3️⃣ **مشكلة تقنية مؤقتة**\n"
                    "   • خوادم Vimeo قد تكون مشغولة\n\n"
                    "💡 **الحلول:**\n"
                    "• جرب فيديو عام آخر\n"
                    "• تأكد من إمكانية المشاهدة بدون تسجيل\n"
                    "• حاول مرة أخرى بعد دقائق",
                    parse_mode='Markdown'
                )
            return

        # ⭐ معالج خاص لأخطاء Dailymotion
        if 'dailymotion' in error_msg.lower() or 'dailymotion.com' in url.lower() or 'dai.ly' in url.lower():
            logger.error(f"❌ [Dailymotion] خطأ في التحميل: {error_msg[:200]}")
            if 'unavailable' in error_msg.lower() or 'not found' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Dailymotion!**\n\n"
                    "🔴 **السبب:** الفيديو غير متاح أو محذوف\n\n"
                    "💡 **الحلول:**\n\n"
                    "1️⃣ **تحقق من الرابط:**\n"
                    "   • افتح الرابط في المتصفح\n"
                    "   • تأكد أن الفيديو لا يزال موجوداً\n\n"
                    "2️⃣ **استخدم الرابط الكامل:**\n"
                    "   • انسخ الرابط من شريط العنوان\n"
                    "   • تجنب الروابط المختصرة dai.ly\n\n"
                    "3️⃣ **جرب محتوى آخر:**\n"
                    "   • بعض الفيديوهات قد تكون محذوفة",
                    parse_mode='Markdown'
                )
            elif 'geo' in error_msg.lower() or 'country' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Dailymotion!**\n\n"
                    "🌍 **السبب:** الفيديو محظور جغرافياً\n\n"
                    "💡 **ملاحظة:**\n"
                    "• بعض محتوى Dailymotion محدود لدول معينة\n"
                    "• أصحاب المحتوى يحددون المناطق المسموحة\n\n"
                    "🔓 **الحل:**\n"
                    "• جرب فيديو آخر متاح عالمياً\n"
                    "• تأكد من إمكانية المشاهدة في منطقتك",
                    parse_mode='Markdown'
                )
            else:
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Dailymotion!**\n\n"
                    "🔴 **الأسباب المحتملة:**\n\n"
                    "1️⃣ **محتوى محظور أو محذوف**\n"
                    "   • تأكد من وجود الفيديو\n\n"
                    "2️⃣ **قيود على الوصول**\n"
                    "   • بعض المحتوى محدود جغرافياً\n\n"
                    "3️⃣ **مشكلة في الرابط**\n"
                    "   • استخدم الرابط الكامل وليس المختصر\n\n"
                    "💡 **الحلول:**\n"
                    "• تحقق من الرابط في المتصفح\n"
                    "• جرب فيديو عام آخر\n"
                    "• استخدم رابط dailymotion.com الكامل",
                    parse_mode='Markdown'
                )
            return

        # ⭐ معالج خاص لأخطاء Twitch
        if 'twitch' in error_msg.lower() or 'twitch.tv' in url.lower():
            logger.error(f"❌ [Twitch] خطأ في التحميل: {error_msg[:200]}")
            if 'subscriber' in error_msg.lower() or 'sub' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Twitch!**\n\n"
                    "👥 **السبب:** المحتوى للمشتركين فقط (Sub-only)\n\n"
                    "💡 **ملاحظة:**\n"
                    "• بعض محتوى Twitch محصور للمشتركين\n"
                    "• VODs القديمة قد تكون محذوفة\n\n"
                    "🔓 **الحل:**\n"
                    "• جرب كليب أو VOD عام آخر\n"
                    "• تأكد من إمكانية المشاهدة بدون اشتراك",
                    parse_mode='Markdown'
                )
            elif 'unavailable' in error_msg.lower() or 'not found' in error_msg.lower() or 'deleted' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Twitch!**\n\n"
                    "🔴 **السبب:** المحتوى محذوف أو منتهي\n\n"
                    "💡 **ملاحظات:**\n\n"
                    "1️⃣ **VODs لها مدة صلاحية:**\n"
                    "   • 14 يوم للمستخدمين العاديين\n"
                    "   • 60 يوم للشركاء والأفلييت\n\n"
                    "2️⃣ **الكليبات قد تُحذف:**\n"
                    "   • صاحب القناة يمكنه حذف الكليبات\n\n"
                    "🔓 **الحلول:**\n"
                    "• تأكد من الرابط في Twitch مباشرة\n"
                    "• جرب VOD أو كليب حديث\n"
                    "• بعض المحتوى قد يكون انتهت صلاحيته",
                    parse_mode='Markdown'
                )
            elif 'live' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل البث من Twitch!**\n\n"
                    "🔴 **السبب:** لا يمكن تحميل البث المباشر\n\n"
                    "💡 **ملاحظة:**\n"
                    "• البث المباشر (Live) لا يمكن تحميله\n"
                    "• يجب انتظار انتهاء البث وتحوله لـ VOD\n\n"
                    "🔓 **الحل:**\n"
                    "• انتظر انتهاء البث\n"
                    "• سيظهر كـ VOD بعد انتهاء البث\n"
                    "• أو حمّل كليب من البث بدلاً من ذلك",
                    parse_mode='Markdown'
                )
            else:
                await processing_message.edit_text(
                    "❌ **فشل تحميل المحتوى من Twitch!**\n\n"
                    "🔴 **الأسباب المحتملة:**\n\n"
                    "1️⃣ **محتوى محذوف أو منتهي**\n"
                    "   • VODs لها مدة صلاحية محدودة\n\n"
                    "2️⃣ **محتوى للمشتركين فقط**\n"
                    "   • بعض المحتوى Sub-only\n\n"
                    "3️⃣ **بث مباشر**\n"
                    "   • لا يمكن تحميل البث الحي\n\n"
                    "4️⃣ **مشكلة في الرابط**\n"
                    "   • تأكد من الرابط الصحيح\n\n"
                    "💡 **الحلول:**\n"
                    "• تحقق من الرابط في Twitch مباشرة\n"
                    "• جرب VOD أو كليب حديث\n"
                    "• تأكد من إمكانية المشاهدة بدون اشتراك",
                    parse_mode='Markdown'
                )
            return

        # ⭐ معالج محسّن لأخطاء Facebook
        if 'facebook' in error_msg.lower() or 'facebook.com' in url.lower() or 'fb.watch' in url.lower() or 'fb.com' in url.lower():
            logger.error(f"❌ [Facebook] خطأ في التحميل: {error_msg[:200]}")

            # معالجة خاصة لـ Facebook Stories - مع Fallback
            if '/stories/' in url.lower() and ('unsupported url' in error_msg.lower() or 'unsupported' in error_msg.lower()):
                # 📝 تفاصيل تقنية للسجلات
                logger.error(f"🔴 [Facebook Story] yt-dlp failed - trying fallback methods...")
                logger.error(f"   URL: {url}")
                logger.error(f"   Error: {error_msg}")

                # 🌐 المحاولة 2: استخدام FB Story Downloader (Fallback)
                try:
                    from core.utils.fb_story_downloader import download_facebook_story
                    import os
                    from datetime import datetime

                    await processing_message.edit_text(
                        "⚠️ **yt-dlp فشل - جاري المحاولة عبر طريقة بديلة...**\n\n"
                        "🌐 استخدام FBDownloader API...",
                        parse_mode='Markdown'
                    )

                    logger.info("🌐 [FB_STORY_FALLBACK] Attempting external downloader...")

                    # محاولة التحميل عبر الموقع الخارجي
                    result = download_facebook_story(url)

                    if result and result.get('video_url'):
                        logger.info(f"✅ [FB_STORY_FALLBACK] Got video URL from {result.get('source')}")

                        await processing_message.edit_text(
                            f"✅ **تم العثور على الفيديو!**\n\n"
                            f"📥 جاري التحميل من {result.get('source')}...",
                            parse_mode='Markdown'
                        )

                        # تحميل الفيديو
                        video_url = result['video_url']
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_file = f"downloads/fb_story_{timestamp}.mp4"

                        # إنشاء مجلد downloads إذا لم يكن موجوداً
                        os.makedirs("downloads", exist_ok=True)

                        # تحميل الملف
                        from core.utils.fb_story_downloader import FBStoryDownloader
                        if FBStoryDownloader.download_file(video_url, output_file):
                            logger.info(f"✅ [FB_STORY_FALLBACK] Downloaded successfully: {output_file}")

                            # إرسال الفيديو
                            await processing_message.edit_text(
                                "📤 **جاري الرفع...**",
                                parse_mode='Markdown'
                            )

                            with open(output_file, 'rb') as video:
                                await context.bot.send_video(
                                    chat_id=update.effective_chat.id,
                                    video=video,
                                    caption=f"📸 Facebook Story\n\n"
                                            f"✅ تم التحميل عبر: {result.get('source')}\n"
                                            f"🌐 طريقة بديلة (Fallback)",
                                    supports_streaming=True
                                )

                            # حذف الملف المؤقت
                            os.remove(output_file)

                            await processing_message.delete()

                            logger.info("✅ [FB_STORY_FALLBACK] Success!")
                            return

                        else:
                            logger.error("❌ [FB_STORY_FALLBACK] File download failed")

                    else:
                        logger.error("❌ [FB_STORY_FALLBACK] No video URL found")

                except Exception as fallback_error:
                    logger.error(f"❌ [FB_STORY_FALLBACK] Error: {fallback_error}")

                # إذا فشل الـ Fallback أيضاً
                await processing_message.edit_text(
                    "❌ **فشل تحميل Facebook Story!**\n\n"
                    "😔 **حاولنا:**\n"
                    "• yt-dlp ❌\n"
                    "• FBDownloader API ❌\n"
                    "• SaveFrom ❌\n\n"
                    "💡 **حلول بديلة:**\n\n"
                    "1️⃣ **تسجيل الشاشة:**\n"
                    "   • استخدم تطبيق Screen Recorder\n\n"
                    "2️⃣ **جرب لاحقاً:**\n"
                    "   • Story قد تكون منتهية أو خاصة\n\n"
                    "3️⃣ **فيديوهات Facebook العادية:**\n"
                    "   • البوت يدعم Posts/Videos بشكل ممتاز ✅",
                    parse_mode='Markdown'
                )
                return

            if 'login' in error_msg.lower() or 'private' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Facebook!**\n\n"
                    "🔒 **السبب:** المحتوى خاص أو يحتاج تسجيل دخول\n\n"
                    "💡 **الحلول:**\n\n"
                    "1️⃣ **تأكد من إعدادات الخصوصية:**\n"
                    "   • الفيديو يجب أن يكون عام (Public)\n"
                    "   • تحقق من إعدادات المنشور\n\n"
                    "2️⃣ **جرب رابط آخر:**\n"
                    "   • انسخ الرابط مباشرة من المتصفح\n"
                    "   • تجنب روابط fb.watch المختصرة\n\n"
                    "3️⃣ **تحديث الكوكيز:**\n"
                    "   • قد تحتاج لتحديث ملفات الكوكيز\n"
                    "   • /admin → إدارة الكوكيز → Facebook",
                    parse_mode='Markdown'
                )
            elif 'unavailable' in error_msg.lower() or 'not found' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Facebook!**\n\n"
                    "🔴 **السبب:** الفيديو غير متاح أو محذوف\n\n"
                    "💡 **الحلول:**\n"
                    "• تأكد أن الفيديو لا يزال موجوداً\n"
                    "• افتح الرابط في Facebook للتحقق\n"
                    "• جرب فيديو عام آخر",
                    parse_mode='Markdown'
                )
            else:
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من Facebook!**\n\n"
                    "🔴 **الأسباب المحتملة:**\n\n"
                    "1️⃣ **محتوى خاص أو محذوف**\n"
                    "   • تحقق من إعدادات الخصوصية\n\n"
                    "2️⃣ **قيود جغرافية**\n"
                    "   • بعض المحتوى محدود لدول معينة\n\n"
                    "3️⃣ **مشكلة في الكوكيز**\n"
                    "   • قد تحتاج لتحديث ملفات الكوكيز\n\n"
                    "💡 **الحلول:**\n"
                    "• تأكد من الرابط في Facebook أولاً\n"
                    "• استخدم رابط facebook.com الكامل\n"
                    "• جرب فيديو عام آخر\n"
                    "• حدّث الكوكيز إذا استمرت المشكلة",
                    parse_mode='Markdown'
                )
            return

        # ⭐ معالج محسّن لأخطاء Twitter/X
        if 'twitter' in error_msg.lower() or 'x.com' in url.lower() or 'twitter.com' in url.lower():
            logger.error(f"❌ [Twitter/X] خطأ في التحميل: {error_msg[:200]}")
            if 'unavailable' in error_msg.lower() or 'not found' in error_msg.lower() or 'deleted' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من X (Twitter)!**\n\n"
                    "🔴 **السبب:** التغريدة محذوفة أو غير متاحة\n\n"
                    "💡 **الحلول:**\n\n"
                    "1️⃣ **تأكد من التغريدة:**\n"
                    "   • افتح الرابط في X/Twitter\n"
                    "   • تحقق أن التغريدة موجودة\n\n"
                    "2️⃣ **تحقق من الحساب:**\n"
                    "   • الحساب قد يكون محذوف أو موقوف\n"
                    "   • تأكد أن الحساب ليس خاصاً\n\n"
                    "3️⃣ **جرب تغريدة أخرى:**\n"
                    "   • بعض التغريدات تُحذف من أصحابها",
                    parse_mode='Markdown'
                )
            elif 'private' in error_msg.lower() or 'protected' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من X (Twitter)!**\n\n"
                    "🔒 **السبب:** الحساب خاص (Protected)\n\n"
                    "💡 **ملاحظة:**\n"
                    "• الحسابات الخاصة تحتاج متابعة\n"
                    "• لا يمكن تحميل محتوى الحسابات المحمية\n\n"
                    "🔓 **الحل:**\n"
                    "• جرب تغريدة من حساب عام\n"
                    "• تأكد أن التغريدة متاحة للجميع",
                    parse_mode='Markdown'
                )
            elif 'age' in error_msg.lower() or 'sensitive' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من X (Twitter)!**\n\n"
                    "🔞 **السبب:** محتوى حساس يتطلب تسجيل دخول\n\n"
                    "💡 **ملاحظة:**\n"
                    "• بعض المحتوى يتطلب تأكيد العمر\n"
                    "• المحتوى الحساس يحتاج كوكيز\n\n"
                    "🔓 **الحل:**\n"
                    "• جرب تغريدة أخرى غير محدودة\n"
                    "• أو حدّث ملفات الكوكيز:\n"
                    "  /admin → إدارة الكوكيز → Twitter",
                    parse_mode='Markdown'
                )
            else:
                await processing_message.edit_text(
                    "❌ **فشل تحميل الفيديو من X (Twitter)!**\n\n"
                    "🔴 **الأسباب المحتملة:**\n\n"
                    "1️⃣ **تغريدة محذوفة**\n"
                    "   • تأكد من وجود التغريدة\n\n"
                    "2️⃣ **حساب خاص أو موقوف**\n"
                    "   • الحسابات المحمية غير متاحة\n\n"
                    "3️⃣ **محتوى حساس**\n"
                    "   • بعض المحتوى يحتاج تسجيل دخول\n\n"
                    "4️⃣ **مشكلة في الرابط**\n"
                    "   • استخدم الرابط الكامل للتغريدة\n\n"
                    "💡 **الحلول:**\n"
                    "• تحقق من الرابط في X/Twitter أولاً\n"
                    "• تأكد من إمكانية المشاهدة بدون تسجيل\n"
                    "• جرب تغريدة عامة أخرى\n"
                    "• حدّث الكوكيز إذا كان محتوى حساس",
                    parse_mode='Markdown'
                )
            return
        
        # رسائل خطأ مخصصة
        if 'private' in error_msg.lower() or 'login' in error_msg.lower():
            await processing_message.edit_text(
                "❌ الفيديو خاص أو يحتاج تسجيل دخول!\n\n"
                "💡 تأكد من أن الفيديو عام ويمكن للجميع مشاهدته."
            )
        elif 'unavailable' in error_msg.lower():
            await processing_message.edit_text(
                "❌ الفيديو غير متاح أو تم حذفه!"
            )
        elif 'geo' in error_msg.lower():
            await processing_message.edit_text(
                "❌ الفيديو محظور جغرافياً في هذه المنطقة!"
            )
        else:
            await processing_message.edit_text(
                f"❌ فشل التحليل!\n\n"
                f"تأكد من أن الرابط صحيح ويمكن الوصول إليه.\n\n"
                f"المنصات المدعومة:\n"
                f"✅ YouTube\n"
                f"✅ Facebook\n"
                f"✅ Instagram\n"
                f"✅ TikTok\n"
                f"✅ Twitter/X\n"
                f"✅ +1000 موقع آخر"
            )

# ===== Per-user cancel download =====
async def cancel_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء التحميل الجاري للمستخدم"""
    user_id = update.effective_user.id
    task = ACTIVE_DOWNLOADS.get(user_id)

    if task and not task.done():
        task.cancel()
        await update.effective_message.reply_text("🛑 طلب الإلغاء تم إرساله. سيتم إيقاف التحميل.")
        logger.info(f"⛔ المستخدم {user_id} ألغى التحميل")
    else:
        await update.effective_message.reply_text("ℹ️ لا يوجد تحميل جارٍ لحسابك حالياً.")

async def cancel_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء التحميل عبر زر inline"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    task = ACTIVE_DOWNLOADS.get(user_id)

    if task and not task.done():
        task.cancel()
        await query.edit_message_text("❌ تم إلغاء التحميل بنجاح.")
        logger.info(f"⛔ المستخدم {user_id} ألغى التحميل عبر زر inline")

        # Cleanup
        PLAYLISTS.pop(user_id, None)
        CANCEL_MESSAGES.pop(user_id, None)
    else:
        await query.answer("⚠️ لا يوجد تحميل جارٍ حالياً.", show_alert=True)

def is_playlist_url(url: str) -> bool:
    """التحقق من أن الرابط هو playlist"""
    return 'playlist' in url.lower() or 'list=' in url.lower()

async def extract_playlist_info(url: str, progress_msg, user_id: int):
    """استخراج معلومات playlist بشكل تفاعلي"""
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True
    }

    try:
        loop = asyncio.get_event_loop()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

        if not playlist_info:
            return None

        entries = playlist_info.get('entries', [])
        if not entries:
            return None

        # Filter out None entries
        entries = [e for e in entries if e]
        total = len(entries)

        # Show interactive analysis progress
        for i, entry in enumerate(entries[:BATCH_MAX_URLS], 1):
            if ACTIVE_DOWNLOADS.get(user_id) and ACTIVE_DOWNLOADS[user_id].cancelled():
                return None

            title = entry.get('title', 'بدون عنوان')
            try:
                cancel_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ إلغاء التحليل", callback_data=f"cancel:{user_id}")]
                ])
                await progress_msg.edit_text(
                    f"📊 جاري تحليل الفيديو {i}/{min(total, BATCH_MAX_URLS)}:\n"
                    f"🎬 {title[:50]}...",
                    reply_markup=cancel_markup
                )
            except Exception:
                pass

            await asyncio.sleep(0.3)  # Small delay for user to see progress

        # Limit to BATCH_MAX_URLS
        entries = entries[:BATCH_MAX_URLS]

        return {
            'title': playlist_info.get('title', 'Playlist'),
            'entries': entries,
            'total': len(entries)
        }

    except Exception as e:
        logger.error(f"❌ خطأ في تحليل playlist: {e}")
        return None

# ===== Batch YouTube download (up to 6 links) =====
async def handle_batch_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج تحميل دفعات من روابط YouTube (حتى 6 روابط)"""
    text = (update.message.text or "").strip()
    urls = YOUTUBE_REGEX.findall(text)

    if not urls:
        await update.message.reply_text(
            "📥 **تحميل دفعات YouTube**\n\n"
            "أرسل حتى 6 روابط يوتيوب في رسالة واحدة لتحميلها على دفعات.\n\n"
            "مثال:\n"
            "https://youtube.com/watch?v=xxxxx\n"
            "https://youtu.be/yyyyy\n"
            "https://youtube.com/watch?v=zzzzz",
            parse_mode="Markdown"
        )
        return

    urls = urls[:BATCH_MAX_URLS]
    user_id = update.effective_user.id
    user = update.effective_user

    # Check if user has an active download
    if ACTIVE_DOWNLOADS.get(user_id) and not ACTIVE_DOWNLOADS[user_id].done():
        await update.message.reply_text("⚠️ لديك تحميل جارٍ بالفعل. انتظر حتى ينتهي أو استخدم /cancel لإلغائه.")
        return

    sem_user = USER_SEMAPHORE[user_id]
    sem_batch = asyncio.Semaphore(PER_USER_BATCH_CONCURRENCY)

    await update.message.reply_text(
        f"🔰 بدء الدفعة ({len(urls)}/{BATCH_MAX_URLS})...\n\n"
        f"يمكنك إرسال /cancel لإلغاء الدفعة الحالية."
    )

    # Track batch download task
    async def _batch_download_flow():
        async with sem_user:
            try:
                async def process_one(url_to_download, idx):
                    async with sem_batch:
                        if ACTIVE_DOWNLOADS.get(user_id) and ACTIVE_DOWNLOADS[user_id].cancelled():
                            logger.info(f"⛔ الدفعة ملغاة للمستخدم {user_id}")
                            return

                        try:
                            logger.info(f"📥 معالجة رابط {idx+1}/{len(urls)}: {url_to_download}")

                            # Reuse existing download logic
                            processing_message = await update.message.reply_text(f"🔍 جاري التحليل ({idx+1}/{len(urls)})...")

                            ydl_opts = get_ydl_opts_for_platform(url_to_download)
                            ydl_opts['skip_download'] = True

                            loop = asyncio.get_event_loop()

                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                info_dict = await loop.run_in_executor(None, lambda: ydl.extract_info(url_to_download, download=False))

                            await processing_message.delete()

                            # Use show_quality_menu or download directly with best quality
                            await show_quality_menu(update, context, url_to_download, info_dict)

                        except asyncio.CancelledError:
                            logger.info(f"⛔ تم إلغاء التحميل {idx+1}")
                            raise
                        except Exception as e:
                            logger.error(f"❌ خطأ في تحميل الرابط {idx+1}: {e}")
                            await update.message.reply_text(f"❌ فشل تحميل الرابط {idx+1}: {url_to_download[:50]}")

                tasks = [asyncio.create_task(process_one(u, i)) for i, u in enumerate(urls)]

                try:
                    await asyncio.gather(*tasks, return_exceptions=False)
                except asyncio.CancelledError:
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    raise

                await update.message.reply_text("✅ اكتملت الدفعة.")

            except asyncio.CancelledError:
                try:
                    await update.message.reply_text("⛔ تم إلغاء الدفعة بناءً على طلبك.")
                except Exception:
                    pass
                raise
            finally:
                if ACTIVE_DOWNLOADS.get(user_id) is task:
                    ACTIVE_DOWNLOADS.pop(user_id, None)

    task = asyncio.create_task(_batch_download_flow(), name=f"batch_download:{user_id}")
    ACTIVE_DOWNLOADS[user_id] = task

# ===== Playlist support with interactive UI =====
async def handle_playlist_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج تحميل playlist YouTube بشكل تفاعلي"""
    user_id = update.effective_user.id
    url = update.message.text.strip()

    # Check if it's a playlist URL
    if not is_playlist_url(url):
        await update.message.reply_text("⚠️ هذا ليس رابط playlist. استخدم /batch للروابط المتعددة.")
        return

    # Check if user has an active download
    if ACTIVE_DOWNLOADS.get(user_id) and not ACTIVE_DOWNLOADS[user_id].done():
        await update.message.reply_text("⚠️ لديك تحميل جارٍ بالفعل. انتظر حتى ينتهي أو استخدم /cancel لإلغائه.")
        return

    progress_msg = await update.message.reply_text("🔍 جاري تحليل قائمة التشغيل...")

    # Track task for cancellation
    async def _playlist_analysis_flow():
        try:
            playlist_info = await extract_playlist_info(url, progress_msg, user_id)

            if not playlist_info:
                await progress_msg.edit_text("❌ فشل تحليل قائمة التشغيل. تأكد من أن الرابط صحيح.")
                return

            total = playlist_info['total']

            # Store playlist info
            PLAYLISTS[user_id] = {
                'entries': playlist_info['entries'],
                'quality': None,
                'progress_msg': progress_msg,
                'url': url
            }

            # Show video selection first
            SELECTED_VIDEOS[user_id] = set(range(1, total + 1))  # Select all by default

            keyboard = []
            for i, entry in enumerate(playlist_info['entries'], start=1):
                title = entry.get('title', f'فيديو {i}')
                keyboard.append([InlineKeyboardButton(
                    f"✅ {i}. {title[:35]}",
                    callback_data=f"toggle_video:{user_id}:{i}"
                )])

            # Add action buttons
            keyboard.append([
                InlineKeyboardButton("📦 تحميل المحدد", callback_data=f"proceed_selection:{user_id}"),
                InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel:{user_id}")
            ])

            await progress_msg.edit_text(
                f"✅ تم تحليل **{total} فيديو** من قائمة التشغيل:\n"
                f"📋 {playlist_info['title'][:50]}\n\n"
                f"اختر الفيديوهات التي تريد تحميلها:\n"
                f"(الكل محدد افتراضياً)",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

        except asyncio.CancelledError:
            try:
                await progress_msg.edit_text("❌ تم إلغاء التحليل.")
            except Exception:
                pass
            raise
        finally:
            if ACTIVE_DOWNLOADS.get(user_id) is task:
                ACTIVE_DOWNLOADS.pop(user_id, None)

    task = asyncio.create_task(_playlist_analysis_flow(), name=f"playlist_analysis:{user_id}")
    ACTIVE_DOWNLOADS[user_id] = task

async def handle_batch_quality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الجودة للدفعة"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data_parts = query.data.split(":")
    quality = data_parts[1]

    playlist_data = PLAYLISTS.get(user_id)
    if not playlist_data:
        await query.edit_message_text("❌ انتهت صلاحية الطلب. أرسل الرابط مرة أخرى.")
        return

    # Check if user has an active download
    if ACTIVE_DOWNLOADS.get(user_id) and not ACTIVE_DOWNLOADS[user_id].done():
        await query.answer("⚠️ لديك تحميل جارٍ بالفعل.", show_alert=True)
        return

    # Get only selected videos
    selected_indices = SELECTED_VIDEOS.get(user_id, set())
    if not selected_indices:
        # If no selection, use all
        selected_indices = set(range(1, len(playlist_data['entries']) + 1))

    entries = [playlist_data['entries'][i-1] for i in sorted(selected_indices)]
    total = len(entries)

    quality_text = {
        'best': 'أفضل جودة',
        'medium': 'جودة متوسطة',
        'audio': 'صوت فقط (MP3)'
    }.get(quality, quality)

    await query.edit_message_text(
        f"✅ تم اختيار: **{quality_text}**\n\n"
        f"📥 جاري تحميل {total} فيديو...",
        parse_mode="Markdown"
    )

    # Start batch download with progress tracking
    async def _batch_download_with_progress():
        try:
            sem_batch = asyncio.Semaphore(PER_USER_BATCH_CONCURRENCY)
            cancel_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⛔ إلغاء التحميل", callback_data=f"cancel:{user_id}")]
            ])

            progress_msg = await context.bot.send_message(
                chat_id=user_id,
                text=f"📦 بدء التحميل... 0/{total} (0%)",
                reply_markup=cancel_markup
            )

            CANCEL_MESSAGES[user_id] = progress_msg

            async def download_single_from_playlist(entry, idx):
                async with sem_batch:
                    if ACTIVE_DOWNLOADS.get(user_id) and ACTIVE_DOWNLOADS[user_id].cancelled():
                        return

                    try:
                        video_url = entry.get('url')
                        if not video_url:
                            video_id = entry.get('id')
                            if video_id:
                                video_url = f"https://www.youtube.com/watch?v={video_id}"
                            else:
                                logger.error(f"❌ لا يمكن الحصول على رابط للفيديو {idx+1}")
                                return

                        title = entry.get('title', 'فيديو')[:30]

                        # Update progress
                        percentage = round(((idx) / total) * 100, 1)
                        try:
                            await progress_msg.edit_text(
                                f"📥 تحميل الفيديو {idx}/{total} ({percentage}%)\n"
                                f"🎬 {title}...",
                                reply_markup=cancel_markup
                            )
                        except Exception:
                            pass

                        # Create a fake update object for download
                        class FakeMessage:
                            def __init__(self, chat_id, message_id, user):
                                self.chat_id = chat_id
                                self.message_id = message_id
                                self.from_user = user
                                self.text = video_url

                            async def reply_text(self, text, **kwargs):
                                return await context.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

                        class FakeUpdate:
                            def __init__(self, chat_id, user):
                                self.effective_chat = type('obj', (object,), {'id': chat_id})()
                                self.effective_user = user
                                self.message = FakeMessage(chat_id, 0, user)
                                self.effective_message = self.message

                        fake_update = FakeUpdate(user_id, query.from_user)

                        # Download with selected quality
                        ydl_opts = get_ydl_opts_for_platform(video_url, quality)
                        ydl_opts['skip_download'] = True

                        loop = asyncio.get_event_loop()
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info_dict = await loop.run_in_executor(None, lambda: ydl.extract_info(video_url, download=False))

                        # Download the video
                        await download_video_with_quality(fake_update, context, video_url, info_dict, quality)

                    except asyncio.CancelledError:
                        logger.info(f"⛔ تم إلغاء التحميل {idx+1}")
                        raise
                    except Exception as e:
                        logger.error(f"❌ خطأ في تحميل الفيديو {idx+1}: {e}")

            tasks = [asyncio.create_task(download_single_from_playlist(e, i+1)) for i, e in enumerate(entries)]

            try:
                await asyncio.gather(*tasks, return_exceptions=False)
            except asyncio.CancelledError:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                raise

            # Final message
            try:
                await progress_msg.edit_text(
                    f"✅ اكتمل تحميل جميع الفيديوهات ({total}/{total})"
                )
            except Exception:
                pass

        except asyncio.CancelledError:
            try:
                if progress_msg:
                    await progress_msg.edit_text("❌ تم إلغاء التحميل.")
            except Exception:
                pass
            raise
        finally:
            PLAYLISTS.pop(user_id, None)
            CANCEL_MESSAGES.pop(user_id, None)
            if ACTIVE_DOWNLOADS.get(user_id) is task:
                ACTIVE_DOWNLOADS.pop(user_id, None)

    task = asyncio.create_task(_batch_download_with_progress(), name=f"batch_download:{user_id}")
    ACTIVE_DOWNLOADS[user_id] = task

# ===== Selective video selection handlers =====
async def toggle_video_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تبديل اختيار فيديو محدد"""
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split(":")
    user_id = int(data_parts[1])
    video_index = int(data_parts[2])

    if query.from_user.id != user_id:
        await query.answer("⚠️ هذا ليس طلبك!", show_alert=True)
        return

    # Toggle selection
    if video_index in SELECTED_VIDEOS[user_id]:
        SELECTED_VIDEOS[user_id].remove(video_index)
    else:
        SELECTED_VIDEOS[user_id].add(video_index)

    # Rebuild keyboard with updated selections
    playlist_data = PLAYLISTS.get(user_id)
    if not playlist_data:
        await query.edit_message_text("❌ انتهت صلاحية الطلب.")
        return

    entries = playlist_data['entries']
    keyboard = []

    for i, entry in enumerate(entries, start=1):
        title = entry.get('title', f'فيديو {i}')
        is_selected = i in SELECTED_VIDEOS[user_id]
        emoji = "✅" if is_selected else "☐"
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {i}. {title[:35]}",
            callback_data=f"toggle_video:{user_id}:{i}"
        )])

    # Add action buttons
    selected_count = len(SELECTED_VIDEOS[user_id])
    keyboard.append([
        InlineKeyboardButton(
            f"📦 تحميل المحدد ({selected_count})",
            callback_data=f"proceed_selection:{user_id}"
        ),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel:{user_id}")
    ])

    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.debug(f"لم يتم تحديث الرسالة: {e}")

async def proceed_to_quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المتابعة إلى اختيار الجودة بعد اختيار الفيديوهات"""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split(":")[1])

    if query.from_user.id != user_id:
        await query.answer("⚠️ هذا ليس طلبك!", show_alert=True)
        return

    selected = SELECTED_VIDEOS.get(user_id, set())

    if not selected:
        await query.answer("⚠️ يجب اختيار فيديو واحد على الأقل!", show_alert=True)
        return

    playlist_data = PLAYLISTS.get(user_id)
    if not playlist_data:
        await query.edit_message_text("❌ انتهت صلاحية الطلب.")
        return

    # Show quality selection
    keyboard = [
        [InlineKeyboardButton("⭐ أفضل جودة", callback_data=f"batch_quality:best:{user_id}")],
        [InlineKeyboardButton("📱 جودة متوسطة (أسرع)", callback_data=f"batch_quality:medium:{user_id}")],
        [InlineKeyboardButton("🎧 صوت فقط (MP3)", callback_data=f"batch_quality:audio:{user_id}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel:{user_id}")]
    ]

    await query.edit_message_text(
        f"✅ تم اختيار **{len(selected)}** فيديو\n\n"
        f"اختر الجودة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )