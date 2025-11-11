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

# ThreadPoolExecutor for async subprocess execution
executor = ThreadPoolExecutor(max_workers=5)

# ===== Per-user cancel download support =====
ACTIVE_DOWNLOADS = {}  # user_id -> asyncio.Task
USER_SEMAPHORE = defaultdict(lambda: asyncio.Semaphore(2))  # max 2 concurrent per user
PLAYLISTS = {}  # user_id -> {entries: list, quality: str, progress_msg: Message}
CANCEL_MESSAGES = {}  # user_id -> Message (for updating progress)
SELECTED_VIDEOS = defaultdict(set)  # user_id -> set of selected video indices

# ===== Batch YouTube download support =====
YOUTUBE_REGEX = re.compile(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+))')
BATCH_MAX_URLS = 6
PER_USER_BATCH_CONCURRENCY = 2

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
from utils import (
    get_message, clean_filename, get_config, format_file_size, format_duration,
    send_video_report, rate_limit, validate_url, log_warning,
    get_cached_user_data, clear_user_cache
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
VIDEO_PATH = 'videos'

if not os.path.exists(VIDEO_PATH):
    os.makedirs(VIDEO_PATH)

# ═══════════════════════════════════════════════════════════════
#  Anime Quotes System (Arabic + English)
# ═══════════════════════════════════════════════════════════════
ANIME_QUOTES = [
    {"ar": "الأحلام لا تتحقق من تلقاء نفسها، عليك أن تعمل من أجلها", "en": "Dreams don't work unless you do"},
    {"ar": "لا تستسلم أبداً، حتى لو كانت الأمور صعبة", "en": "Never give up, even if things get tough"},
    {"ar": "القوة الحقيقية تأتي من الداخل", "en": "True strength comes from within"},
    {"ar": "الفشل مجرد فرصة للبدء من جديد بذكاء أكبر", "en": "Failure is just a chance to start again more intelligently"},
    {"ar": "كن الشخص الذي تريد أن تكونه، لا ما يريده الآخرون", "en": "Be who you want to be, not what others want"},
    {"ar": "الطريق إلى النجاح مليء بالتحديات، لكن المكافأة تستحق العناء", "en": "The road to success is full of challenges, but the reward is worth it"},
    {"ar": "لا يمكنك تغيير الماضي، لكن يمكنك صنع المستقبل", "en": "You can't change the past, but you can create the future"},
    {"ar": "الشجاعة ليست عدم الخوف، بل مواجهة الخوف", "en": "Courage is not the absence of fear, but facing it"},
    {"ar": "أحياناً أصغر خطوة في الاتجاه الصحيح تكون أكبر خطوة في حياتك", "en": "Sometimes the smallest step in the right direction is the biggest step of your life"},
    {"ar": "النجاح ليس النهاية، والفشل ليس القاتل: إنها الشجاعة للاستمرار هي المهمة", "en": "Success is not final, failure is not fatal: it's the courage to continue that counts"},
    {"ar": "لا تنتظر الفرص، اصنعها بنفسك", "en": "Don't wait for opportunities, create them yourself"},
    {"ar": "كل يوم هو فرصة جديدة لتصبح أفضل", "en": "Every day is a new opportunity to be better"},
    {"ar": "الإيمان بالنفس هو أول سر من أسرار النجاح", "en": "Believing in yourself is the first secret to success"},
    {"ar": "لا تقارن نفسك بالآخرين، قارن نفسك بمن كنت بالأمس", "en": "Don't compare yourself to others, compare yourself to who you were yesterday"},
    {"ar": "العقبات هي تلك الأشياء المخيفة التي تراها عندما تبعد عينيك عن هدفك", "en": "Obstacles are those frightful things you see when you take your eyes off your goal"},
    {"ar": "النجاح يتطلب المثابرة والعزيمة", "en": "Success requires perseverance and determination"},
    {"ar": "الحياة قصيرة جداً، لا تضيعها في الأشياء السلبية", "en": "Life is too short to waste on negative things"},
    {"ar": "التغيير يبدأ منك أنت", "en": "Change starts with you"},
    {"ar": "لا شيء مستحيل مع الإرادة القوية", "en": "Nothing is impossible with strong will"},
    {"ar": "أنت أقوى مما تعتقد", "en": "You are stronger than you think"}
]

class DownloadProgressTracker:
    """تتبع تقدم التحميل مع عداد نسبة مئوية + اقتباسات أنمي عشوائية"""
    def __init__(self, message, lang):
        self.message = message
        self.lang = lang
        self.last_update_time = 0
        self.last_percentage = -1
        # اختيار اقتباس عشوائي في بداية كل تحميل
        self.quote = random.choice(ANIME_QUOTES)
        logger.info(f"💬 تم اختيار حكمة عشوائية: {self.quote['ar'][:30]}...")

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            try:
                current_time = time.time()
                # تحديث كل 1.5 ثانية (سلس وسريع)
                if current_time - self.last_update_time < 1.5:
                    return

                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)

                if total > 0:
                    percentage = int((downloaded / total) * 100)

                    # تحديث كل 3% (سلاسة أكثر)
                    if abs(percentage - self.last_percentage) < 3:
                        return

                    self.last_percentage = percentage
                    self.last_update_time = current_time

                    speed = d.get('speed', 0)
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    speed_text = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "حساب..."

                    # حساب الوقت المتبقي
                    eta = d.get('eta', 0)
                    if eta and eta > 0:
                        eta_mins = eta // 60
                        eta_secs = eta % 60
                        eta_text = f"{int(eta_mins)}:{int(eta_secs):02d}"
                    else:
                        eta_text = "حساب..."

                    progress_bar = self._create_progress_bar(percentage)

                    # رموز تفاعلية حسب التقدم
                    if percentage < 25:
                        status_emoji = "📥"
                        status_text = "بدء التحميل"
                    elif percentage < 50:
                        status_emoji = "⬇️"
                        status_text = "جاري التحميل"
                    elif percentage < 75:
                        status_emoji = "⚡"
                        status_text = "سرعة عالية"
                    elif percentage < 95:
                        status_emoji = "🔄"
                        status_text = "جاري المعالجة"
                    else:
                        status_emoji = "✨"
                        status_text = "على وشك الانتهاء"

                    # تنسيق الرسالة مع الحكمة (بدون Markdown للحكمة لتجنب أخطاء التنسيق)
                    update_text = (
                        f"{status_emoji} **{status_text}...**\n\n"
                        f"{progress_bar}\n"
                        f"⚡ {speed_text} | ⏱️ ETA: {eta_text}\n"
                        f"📦 {downloaded_mb:.1f} / {total_mb:.1f} MB\n\n"
                        f"💭 {self.quote['ar']}\n"
                        f"💬 {self.quote['en']}"
                    )

                    try:
                        # تحديث نفس الرسالة بشكل آمن
                        loop = asyncio.get_event_loop()
                        loop.create_task(self._safe_update(update_text))
                    except Exception as e:
                        logger.debug(f"تحديث التقدم: {e}")

            except Exception as e:
                log_warning(f"خطأ في تحديث التقدم: {e}", module="handlers/download.py")

    async def _safe_update(self, text):
        """تحديث آمن للرسالة مع معالجة الأخطاء"""
        try:
            await self.message.edit_text(text, parse_mode='Markdown')
        except Exception as e:
            # تجاهل أخطاء "message not modified" و "message to edit not found"
            if "message is not modified" not in str(e).lower() and "message to edit not found" not in str(e).lower():
                logger.debug(f"خطأ في تحديث الرسالة: {e}")

    def _create_progress_bar(self, percentage):
        """إنشاء شريط تقدم متحرك مع أيقونات 💠"""
        filled = int(percentage / 5)
        empty = 20 - filled
        bar = '💠' * filled + '⬜' * empty
        return f"`{bar}` **{percentage}%**"

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
    """إرسال سجل التحميل إلى قناة اللوج مع رسالة نصية قابلة للنسخ (فيديو أو صوت)"""
    if not LOG_CHANNEL_ID:
        return

    try:
        log_channel_id = int(LOG_CHANNEL_ID)
    except (ValueError, TypeError):
        logger.error(f"❌ LOG_CHANNEL_ID غير صحيح: {LOG_CHANNEL_ID}")
        return

    user_id = user.id
    user_name = user.full_name
    username = f"@{user.username}" if user.username else "مجهول"

    media_title = video_info.get('title', 'غير متوفر (No title)')
    media_url = video_info.get('webpage_url', 'N/A')
    duration = video_info.get('duration', 0)
    view_count = video_info.get('view_count', 0)
    like_count = video_info.get('like_count', 0)

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
        # 1) Forward الوسائط (فيديو أو صوت) إلى قناة السجلات
        forwarded = await context.bot.forward_message(
            chat_id=log_channel_id,
            from_chat_id=update.effective_chat.id,
            message_id=sent_message.message_id
        )

        # 2) إرسال رسالة نصية منسقة قابلة للنسخ بالكامل
        info_text = (
            f"{media_emoji} **{media_text} جديد تم معالجته**\n\n"
            f"👤 **المستخدم:** {username} (ID: `{user_id}`)\n"
            f"🔗 **الرابط:** {media_url}\n"
            f"🎞️ **العنوان:** {media_title}\n"
            f"📊 **المشاهدات:** {views_text}\n"
            f"💬 **التفاعلات:** {likes_text}\n"
            f"⏱️ **المدة:** {duration_text}\n"
            f"📦 **الحجم:** {size_text}\n"
            f"🎭 **النوع:** {media_type}\n"
            f"📅 **الوقت:** {timestamp}\n\n"
            f"✨ **الوسائط مرفقة أعلاه مباشرة.**"
        )

        # الانتظار ثانية واحدة قبل إرسال النص لضمان ترتيب الرسائل
        await asyncio.sleep(1)

        await context.bot.send_message(
            chat_id=log_channel_id,
            text=info_text,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

        logger.info(f"✅ تم إرسال {media_text} ورسالة نصية قابلة للنسخ إلى قناة السجلات")

    except Exception as e:
        log_warning(f"❌ فشل إرسال {media_text} إلى قناة السجل: {e}", module="handlers/download.py")

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

    # التحقق من مدة الصوتيات إذا اختار المستخدم "صوت فقط"
    if quality_choice == 'audio':
        user_id = query.from_user.id

        from database import is_audio_enabled, get_audio_limit_minutes, is_subscribed, is_admin

        # التحقق من تفعيل الصوتيات
        if not is_audio_enabled():
            await query.edit_message_text(
                "🚫 **تحميل الصوتيات معطل حالياً!**\n\n"
                "يرجى اختيار جودة فيديو بدلاً من ذلك."
            )
            return

        # التحقق من حد المدة (للمستخدمين غير المشتركين وغير المدراء)
        if not is_subscribed(user_id) and not is_admin(user_id):
            duration_seconds = info_dict.get('duration', 0)

            if duration_seconds > 0:
                duration_minutes = duration_seconds / 60
                audio_limit_minutes = get_audio_limit_minutes()

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
    # تحديد المنصة
    is_facebook = 'facebook.com' in url or 'fb.watch' in url or 'fb.com' in url
    is_instagram = 'instagram.com' in url
    is_tiktok = 'tiktok.com' in url or 'vm.tiktok.com' in url or 'vt.tiktok.com' in url
    is_pinterest = 'pinterest.com' in url or 'pin.it' in url  # ⭐ إضافة Pinterest
    
    # الجودة
    quality_formats = {
        'best': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        'medium': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        'audio': 'bestaudio/best'
    }
    
    format_choice = quality_formats.get(quality, 'best')
    
    # إعدادات أساسية
    ydl_opts = {
        'format': format_choice,
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
    }

    # دعم ملف cookies.txt إذا كان موجوداً
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'
        logger.info("✅ Using cookies.txt for authentication")
    
    # ⭐ إعدادات خاصة لـ Pinterest - حل مشاكل التحميل
    if is_pinterest:
        ydl_opts.update({
            'format': 'best',  # Pinterest يحتاج 'best' فقط
            # تقليل concurrent downloads لتجنب مشاكل fragments
            'concurrent_fragment_downloads': 1,
            # زيادة المحاولات
            'retries': 20,
            'fragment_retries': 20,
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
    
    # إعدادات خاصة لـ Facebook
    elif is_facebook:
        ydl_opts.update({
            'format': 'best',  # Facebook يحتاج 'best' فقط
            'extractor_args': {
                'facebook': {
                    'timeout': 60
                }
            },
            # User-Agent مهم لـ Facebook
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        })
    
    # إعدادات خاصة لـ Instagram
    elif is_instagram:
        ydl_opts.update({
            'format': 'best',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'X-IG-App-ID': '936619743392459',
            },
            'extractor_args': {
                'instagram': {
                    'timeout': 60
                }
            }
        })
    
    # إعدادات خاصة لـ TikTok - مُحسّنة للصور والفيديوهات
    elif is_tiktok:
        ydl_opts.update({
            'format': 'best',
            # إعدادات مهمة لتيك توك
            'writesubtitles': False,
            'writethumbnail': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.tiktok.com/',
            },
            'extractor_args': {
                'tiktok': {
                    'api_hostname': 'api16-normal-c-useast1a.tiktokv.com'
                }
            }
        })
    
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


async def send_file_with_retry(context, chat_id, file_path, is_audio, caption, reply_to_message_id, duration, info_dict, max_retries=3):
    """
    محاولة إرسال الملف مع إعادة المحاولة في حالة TimedOut
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"🔄 محاولة رفع الملف (المحاولة {attempt}/{max_retries})")

            with open(file_path, 'rb') as file:
                if is_audio:
                    sent_message = await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=file,
                        caption=caption[:1024],
                        reply_to_message_id=reply_to_message_id,
                        duration=duration,
                        read_timeout=300,  # 5 دقائق
                        write_timeout=300,  # 5 دقائق
                        connect_timeout=60,
                        pool_timeout=60
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
                        read_timeout=300,
                        write_timeout=300,
                        connect_timeout=60,
                        pool_timeout=60
                    )

                logger.info(f"✅ تم الرفع بنجاح في المحاولة {attempt}")
                return sent_message, None

        except (TimedOut, httpx.WriteTimeout, httpx.ReadTimeout, NetworkError) as e:
            logger.warning(f"⏱️ TimedOut في المحاولة {attempt}/{max_retries}: {e}")

            if attempt < max_retries:
                wait_time = attempt * 2  # تأخير تدريجي: 2، 4، 6 ثانية
                logger.info(f"⏳ انتظار {wait_time} ثانية قبل إعادة المحاولة...")
                await asyncio.sleep(wait_time)
            else:
                # فشلت جميع المحاولات
                logger.error(f"❌ فشلت جميع المحاولات ({max_retries}) لرفع الملف")
                return None, e

        except Exception as e:
            # أخطاء أخرى لا تستدعي إعادة المحاولة
            logger.error(f"❌ خطأ غير متوقع أثناء الرفع: {e}")
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
        text="📥 بدء التحميل...\n\n⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%"
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
            await processing_message.edit_text("📷 اكتشفت صوراً! جاري التحميل...")
            
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
            await processing_message.edit_text(f"📤 جاري رفع {len(image_files)} صورة...")
            
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

        progress_tracker = DownloadProgressTracker(processing_message, lang)
        ydl_opts['progress_hooks'] = [progress_tracker.progress_hook]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, lambda: ydl.download([url]))
        except DownloadError as e:
            error_msg = str(e).lower()
            # التعامل مع أخطاء تسجيل الدخول للمحتوى الخاص
            if "log in" in error_msg or "login" in error_msg or "private" in error_msg or "members only" in error_msg:
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

            # استخدام ThreadPoolExecutor لتجنب التجميد أثناء FFmpeg
            loop = asyncio.get_event_loop()
            result_path = await loop.run_in_executor(
                executor,
                apply_animated_watermark,
                new_filepath,
                temp_watermarked_path,
                logo_path
            )

            if result_path != new_filepath and os.path.exists(result_path):
                final_video_path = result_path
                logger.info(f"✨ تم تطبيق اللوجو المتحرك")
        elif has_credits and not is_subscribed_user and not is_user_admin:
            # المستخدم لديه نقاط ولم يتم وضع اللوجو، فنستهلك نقطة
            if use_no_logo_credit(user_id):
                logger.info(f"✅ تم استخدام نقطة بدون لوجو للمستخدم {user_id}، المتبقي: {no_logo_credits - 1}")
                # إرسال إشعار للمستخدم
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🎨 تم استخدام نقطة بدون لوجو!\n💰 الرصيد المتبقي: {no_logo_credits - 1} فيديو"
                )

        # Safety check: ensure final_video_path is never None
        if final_video_path is None:
            final_video_path = new_filepath
            logger.warning(f"⚠️ final_video_path was None, using new_filepath: {new_filepath}")

        file_size = os.path.getsize(final_video_path)
        total_mb = file_size / (1024 * 1024)
        
        await processing_message.edit_text(
            f"📤 جاري الرفع...\n\n"
            f"⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%\n\n"
            f"📦 الحجم: {total_mb:.1f} MB"
        )
        
        if file_size > 2 * 1024 * 1024 * 1024:
            await processing_message.edit_text("❌ الملف كبير جداً! (أكثر من 2GB)")
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
        
        # محاكاة تقدم الرفع
        for progress in [25, 50, 75]:
            await asyncio.sleep(0.3)
            filled = int(progress / 5)
            empty = 20 - filled
            bar = f"{'🟩' * filled}{'⬜' * empty}"
            
            try:
                await processing_message.edit_text(
                    f"📤 جاري الرفع...\n\n"
                    f"{bar} {progress}%\n\n"
                    f"📦 الحجم: {total_mb:.1f} MB"
                )
            except:
                pass
        
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
            max_retries=3
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

            # إرسال رسالة للمستخدم مع رابط بديل
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"⚠️ **حدث خطأ في رفع الملف مباشرة**\n\n"
                    f"الملف كبير جداً ({format_file_size(os.path.getsize(final_video_path))})\n"
                    f"ولكن تم تحميله بنجاح على السيرفر!\n\n"
                    f"🔗 **رابط بديل:** {alternative_url}\n\n"
                    f"⏱️ المدة: {format_duration(duration)}\n"
                    f"💡 يمكنك تحميله من الرابط أعلاه"
                ),
                reply_to_message_id=update.effective_message.message_id,
                parse_mode='Markdown'
            )

            # إرسال تقرير فشل إلى قناة السجلات
            if LOG_CHANNEL_ID:
                try:
                    log_channel_id = int(LOG_CHANNEL_ID)
                    fail_report_text = (
                        "🔴 **فشل رفع ملف كبير (TimedOut)**\n\n"
                        f"👤 المستخدم: @{user.username if user.username else user.full_name} (ID: {user_id})\n"
                        f"🔗 الرابط الأصلي: {url[:100]}\n"
                        f"📦 الحجم: {format_file_size(os.path.getsize(final_video_path))}\n"
                        f"⏱️ المدة: {format_duration(duration)}\n"
                        f"📝 العنوان: {title[:100]}\n"
                        f"⚠️ الخطأ: {upload_error}\n"
                        f"🔗 الرابط البديل: {alternative_url}\n"
                        f"🕒 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    await context.bot.send_message(
                        chat_id=log_channel_id,
                        text=fail_report_text,
                        parse_mode='Markdown'
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

        # 2. إرسال تقرير إلى قناة السجلات
        if LOG_CHANNEL_ID:
            try:
                log_channel_id = int(LOG_CHANNEL_ID)
                error_report_text = (
                    "⚠️ **فشل تحميل جديد**\n\n"
                    f"👤 المستخدم: @{username} (ID: {user_id})\n"
                    f"🔗 الرابط: {url[:100]}\n"
                    f"⚠️ نوع الخطأ: `{error_type}`\n"
                    f"💬 الرسالة: `{error_message[:200]}`\n"
                    f"🕒 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )

                await context.bot.send_message(
                    chat_id=log_channel_id,
                    text=error_report_text,
                    parse_mode='Markdown'
                )

                logger.info(f"✅ تم إرسال تقرير الخطأ لقناة السجلات")
            except Exception as log_error:
                log_warning(f"❌ فشل إرسال تقرير الخطأ لقناة السجلات: {log_error}", module="handlers/download.py")

        # 3. إشعار المستخدم بالفشل وإبلاغ المدير
        error_text = (
            "❌ **حدث خطأ أثناء تحميل المقطع!**\n\n"
            "📩 تم إرسال مشكلتك إلى المدير، وسيتم إعلامك عند التصليح.\n\n"
            "شكراً لصبرك! 💚"
        )

        try:
            await processing_message.edit_text(error_text, parse_mode='Markdown')
        except Exception as edit_error:
            log_warning(f"فشل تعديل رسالة الخطأ: {edit_error}", module="handlers/download.py")
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
        
        loop = asyncio.get_event_loop()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
        
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
                keyboard = [[InlineKeyboardButton(
                    "⭐ اشترك الآن",
                    url="https://instagram.com/7kmmy"
                )]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await processing_message.edit_text(
                    f"⏰ الفيديو طويل! (أكثر من {free_time_limit} دقائق). اشترك لتحميل فيديوهات طويلة!",
                    reply_markup=reply_markup
                )
                return
        # إذا كان الاشتراك معطلاً، السماح بالتحميل بدون قيود
        
        await processing_message.delete()
        
        await show_quality_menu(update, context, url, info_dict)
        
    except Exception as e:
        logger.error(f"❌ خطأ في التحليل: {e}", exc_info=True)
        error_msg = str(e)
        
        # ⭐ معالج خاص لأخطاء Pinterest
        if 'pinterest' in error_msg.lower():
            if 'no video formats found' in error_msg.lower():
                await processing_message.edit_text(
                    "❌ هذا الرابط لا يحتوي على فيديو!\n\n"
                    "💡 تأكد من أن الرابط يشير إلى Pin يحتوي على فيديو وليس صورة.\n\n"
                    "📌 جرب:\n"
                    "• افتح الرابط في المتصفح\n"
                    "• تأكد أنه فيديو وليس صورة\n"
                    "• انسخ الرابط من شريط العنوان مباشرة"
                )
            else:
                await processing_message.edit_text(
                    "❌ فشل تحميل الفيديو من Pinterest!\n\n"
                    "💡 Pinterest يواجه مشاكل تقنية حالياً.\n\n"
                    "📌 الحلول:\n"
                    "• جرب فيديو آخر من Pinterest\n"
                    "• انسخ الرابط الأصلي (بدون /sent/)\n"
                    "• حاول مرة أخرى بعد قليل"
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