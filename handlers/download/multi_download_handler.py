"""
معالج التحميل المتعدد الشامل (Multi-Download Handler)
يدعم: تحميل متعدد، صوت، فيديو، إلغاء، استئناف، ضغط تلقائي
"""

import os
import re
import asyncio
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import yt_dlp

from database import get_user_language, record_download_attempt, track_download
from utils import log_warning, send_critical_log, log_error_to_file

logger = logging.getLogger(__name__)

# ThreadPoolExecutor for async subprocess execution
executor = ThreadPoolExecutor(max_workers=5)

# مجلد التحميلات
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# الحد الأقصى للروابط
MAX_LINKS = 6

# حد حجم Telegram (50MB)
TELEGRAM_MAX_SIZE = 50 * 1024 * 1024


# ═══════════════════════════════════════════════════════════════
#  URL Detection & Validation
# ═══════════════════════════════════════════════════════════════

def extract_urls(text: str) -> List[str]:
    """استخراج جميع الروابط من النص"""
    # بحث عن روابط YouTube, Instagram, Facebook, etc.
    url_pattern = r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|instagram\.com/(?:p|reel|stories)/|fb\.watch/|facebook\.com/(?:stories/|watch/)?)[^\s]+'
    urls = re.findall(url_pattern, text)
    return urls[:MAX_LINKS]  # حد أقصى 6 روابط


def detect_platform(url: str) -> str:
    """تحديد المنصة من الرابط"""
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    elif 'instagram.com/reel' in url or 'instagram.com/p' in url:
        return 'instagram_post'
    elif 'instagram.com/stories' in url:
        return 'instagram_story'
    elif 'facebook.com/stories' in url:
        return 'facebook_story'
    elif 'facebook.com' in url or 'fb.watch' in url:
        return 'facebook'
    else:
        return 'unknown'


# ═══════════════════════════════════════════════════════════════
#  Mode Selection (Video / Audio)
# ═══════════════════════════════════════════════════════════════

async def show_mode_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, urls: List[str]):
    """عرض اختيار الوضع (فيديو أو صوت)"""
    user_id = update.effective_user.id
    lang = get_user_language(user_id)

    # حفظ الروابط في context
    context.user_data['pending_urls'] = urls
    context.user_data['download_mode'] = None

    message_text = (
        f"🎥 **وضع التحميل / Download Mode**\n\n"
        f"📊 عدد الروابط / Links found: {len(urls)}\n\n"
        f"اختر الوضع المطلوب:\n"
        f"Select download mode:"
    )

    keyboard = [
        [InlineKeyboardButton("🎞️ تحميل فيديو / Video Download", callback_data="mode_video")],
        [InlineKeyboardButton("🎧 تحميل صوت فقط / Audio Only", callback_data="mode_audio")],
        [InlineKeyboardButton("❌ إلغاء / Cancel", callback_data="download_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# ═══════════════════════════════════════════════════════════════
#  Quality Selection (Video)
# ═══════════════════════════════════════════════════════════════

async def show_quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض اختيار جودة الفيديو"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang = get_user_language(user_id)

    context.user_data['download_mode'] = 'video'

    message_text = (
        "📺 **اختيار الجودة / Quality Selection**\n\n"
        "اختر جودة الفيديو:\n"
        "Select video quality:"
    )

    keyboard = [
        [InlineKeyboardButton("360p (صغير / Small)", callback_data="quality_360")],
        [InlineKeyboardButton("720p HD (متوسط / Medium)", callback_data="quality_720")],
        [InlineKeyboardButton("1080p Full HD (كبير / Large)", callback_data="quality_1080")],
        [InlineKeyboardButton("🔙 رجوع / Back", callback_data="download_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# ═══════════════════════════════════════════════════════════════
#  Audio Format Selection
# ═══════════════════════════════════════════════════════════════

async def show_audio_format_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض اختيار صيغة الصوت"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang = get_user_language(user_id)

    context.user_data['download_mode'] = 'audio'

    message_text = (
        "🎧 **نوع الصوت / Audio Format**\n\n"
        "اختر صيغة الملف الصوتي:\n"
        "Select audio format:"
    )

    keyboard = [
        [InlineKeyboardButton("MP3 (مضغوط، صغير / Compressed, Small)", callback_data="audio_mp3")],
        [InlineKeyboardButton("M4A (جودة عالية / High Quality)", callback_data="audio_m4a")],
        [InlineKeyboardButton("🔙 رجوع / Back", callback_data="download_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# ═══════════════════════════════════════════════════════════════
#  Download Progress Tracker
# ═══════════════════════════════════════════════════════════════

class MultiDownloadProgress:
    """تتبع تقدم التحميل المتعدد"""

    def __init__(self, message, total_files: int, mode: str, lang: str):
        self.message = message
        self.total_files = total_files
        self.mode = mode
        self.lang = lang
        self.current_file = 0
        self.current_progress = 0
        self.last_update_time = 0
        self.is_uploading = False

    def progress_hook(self, d):
        """معالج التقدم من yt-dlp"""
        import time

        if d['status'] == 'downloading':
            current_time = time.time()

            # تحديث كل ثانيتين فقط
            if current_time - self.last_update_time < 2:
                return

            self.last_update_time = current_time

            try:
                # حساب النسبة المئوية
                if 'total_bytes' in d:
                    total = d['total_bytes']
                elif 'total_bytes_estimate' in d:
                    total = d['total_bytes_estimate']
                else:
                    total = 0

                downloaded = d.get('downloaded_bytes', 0)

                if total > 0:
                    self.current_progress = int((downloaded / total) * 100)

                # عرض التقدم
                progress_bar = self._create_progress_bar(self.current_progress)

                mode_text = "🎵 Audio" if self.mode == 'audio' else "🎥 Video"

                update_text = (
                    f"{mode_text} ({self.current_file + 1}/{self.total_files})\n\n"
                    f"⬇️ {'جاري التحميل' if self.lang == 'ar' else 'Downloading'}: {self.current_progress}%\n"
                    f"{progress_bar}\n"
                )

                # تحديث الرسالة بشكل آمن
                loop = asyncio.get_event_loop()
                loop.create_task(self._safe_update(update_text))

            except Exception as e:
                logger.debug(f"Progress update error: {e}")

    async def _safe_update(self, text: str):
        """تحديث آمن للرسالة مع زر الإلغاء"""
        try:
            # إضافة زر الإلغاء
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [[
                InlineKeyboardButton(
                    "❌ إلغاء التحميل / Cancel Download",
                    callback_data="download_cancel"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await self.message.edit_text(text, reply_markup=reply_markup)
        except Exception:
            pass

    def _create_progress_bar(self, percentage: int) -> str:
        """إنشاء شريط تقدم بتصميم محسّن"""
        # استخدام ▓ للجزء المكتمل و ░ للجزء المتبقي
        filled = int(percentage / 10)  # 10 مربعات (كل 10%)
        empty = 10 - filled
        return f"{'▓' * filled}{'░' * empty} {percentage}%"

    async def set_uploading(self, file_num: int):
        """تعيين حالة الرفع"""
        self.is_uploading = True
        self.current_file = file_num

        mode_text = "🎵 Audio" if self.mode == 'audio' else "🎥 Video"

        text = (
            f"{mode_text} ({file_num + 1}/{self.total_files})\n\n"
            f"📤 {'جاري الرفع إلى Telegram' if self.lang == 'ar' else 'Uploading to Telegram'}...\n"
            "⏳ Please wait..."
        )

        await self._safe_update(text)


# ═══════════════════════════════════════════════════════════════
#  Video Download
# ═══════════════════════════════════════════════════════════════

async def download_videos(update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
    """تحميل الفيديوهات"""
    query = update.callback_query
    user_id = query.from_user.id
    lang = get_user_language(user_id)

    urls = context.user_data.get('pending_urls', [])
    if not urls:
        await query.answer("❌ No URLs found", show_alert=True)
        return

    quality_height = quality.replace('quality_', '')

    # رسالة التقدم
    progress_message = await query.edit_message_text(
        f"🎬 {'جاري التحضير' if lang == 'ar' else 'Preparing'}...\n"
        f"📊 Total: {len(urls)} videos"
    )

    progress_tracker = MultiDownloadProgress(progress_message, len(urls), 'video', lang)

    # خيارات yt-dlp
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': f'best[height<={quality_height}]',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'continuedl': True,
        'progress_hooks': [progress_tracker.progress_hook],
    }

    successful = 0
    failed = 0

    for idx, url in enumerate(urls):
        # التحقق من الإلغاء
        if context.user_data.get('cancel_download'):
            # تسجيل الروابط المتبقية كملغاة
            for remaining_url in urls[idx:]:
                platform = detect_platform(remaining_url)
                track_download(
                    user_id=query.from_user.id,
                    platform=platform,
                    mode='video',
                    quality=quality_height,
                    status='canceled',
                    url=remaining_url
                )

            await progress_message.edit_text(
                "❌ تم إلغاء التحميل / Download canceled"
            )
            return

        progress_tracker.current_file = idx

        try:
            # تحميل الفيديو
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

            # التحقق من الحجم والضغط إذا لزم الأمر
            file_size = os.path.getsize(filename)

            if file_size > TELEGRAM_MAX_SIZE:
                # ضغط الفيديو
                await progress_message.edit_text(
                    f"⚙️ {'جاري الضغط' if lang == 'ar' else 'Compressing'}...\n"
                    f"File {idx + 1}/{len(urls)}"
                )

                compressed_file = await compress_video(filename)
                if compressed_file:
                    os.remove(filename)
                    filename = compressed_file

            # رفع إلى Telegram
            await progress_tracker.set_uploading(idx)

            with open(filename, 'rb') as video:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=video,
                    caption=f"🎥 {info.get('title', 'Video')}\n📊 Quality: {quality_height}p",
                    supports_streaming=True
                )

            # حذف الملف
            file_size_bytes = os.path.getsize(filename) if os.path.exists(filename) else 0
            os.remove(filename)
            successful += 1

            # تسجيل مفصل في قاعدة البيانات (Mission 10)
            platform = detect_platform(url)
            track_download(
                user_id=query.from_user.id,
                platform=platform,
                mode='video',
                quality=quality_height,
                status='completed',
                url=url,
                file_size=file_size_bytes
            )
            record_download_attempt(success=True, speed=0)

        except Exception as e:
            logger.error(f"Download error for {url}: {e}")
            log_warning(f"فشل تحميل فيديو: {url} - {str(e)}", module="multi_download_handler")

            # Mission 11: Enhanced error logging
            log_error_to_file("video_download", query.from_user.id, url, e)

            failed += 1

            # تسجيل الفشل
            platform = detect_platform(url)
            track_download(
                user_id=query.from_user.id,
                platform=platform,
                mode='video',
                quality=quality_height,
                status='failed',
                url=url,
                error_msg=str(e)
            )
            record_download_attempt(success=False, speed=0)

    # رسالة النهاية
    final_text = (
        f"✅ **{'اكتمل التحميل' if lang == 'ar' else 'Download Complete'}!**\n\n"
        f"✔️ {'ناجح' if lang == 'ar' else 'Successful'}: {successful}\n"
        f"❌ {'فاشل' if lang == 'ar' else 'Failed'}: {failed}\n"
        f"📊 {'الإجمالي' if lang == 'ar' else 'Total'}: {len(urls)}"
    )

    await progress_message.edit_text(final_text, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
#  Audio Download
# ═══════════════════════════════════════════════════════════════

async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, audio_format: str):
    """تحميل الصوتيات"""
    query = update.callback_query
    user_id = query.from_user.id
    lang = get_user_language(user_id)

    urls = context.user_data.get('pending_urls', [])
    if not urls:
        await query.answer("❌ No URLs found", show_alert=True)
        return

    format_codec = audio_format.replace('audio_', '')

    # رسالة التقدم
    progress_message = await query.edit_message_text(
        f"🎵 {'جاري التحضير' if lang == 'ar' else 'Preparing'}...\n"
        f"📊 Total: {len(urls)} audio files"
    )

    progress_tracker = MultiDownloadProgress(progress_message, len(urls), 'audio', lang)

    # خيارات yt-dlp للصوت
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format_codec,
            'preferredquality': '192',
        }],
        'continuedl': True,
        'progress_hooks': [progress_tracker.progress_hook],
    }

    successful = 0
    failed = 0

    for idx, url in enumerate(urls):
        # التحقق من الإلغاء
        if context.user_data.get('cancel_download'):
            # تسجيل الروابط المتبقية كملغاة
            for remaining_url in urls[idx:]:
                platform = detect_platform(remaining_url)
                track_download(
                    user_id=query.from_user.id,
                    platform=platform,
                    mode='audio',
                    format=format_codec,
                    status='canceled',
                    url=remaining_url
                )

            await progress_message.edit_text(
                "❌ تم إلغاء التحميل / Download canceled"
            )
            return

        progress_tracker.current_file = idx

        try:
            # تحميل الصوت
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # الاسم النهائي بعد التحويل
                base_filename = ydl.prepare_filename(info)
                filename = os.path.splitext(base_filename)[0] + f'.{format_codec}'

            # رفع إلى Telegram
            await progress_tracker.set_uploading(idx)

            with open(filename, 'rb') as audio:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=audio,
                    caption=f"🎵 {info.get('title', 'Audio')}\n📊 Format: {format_codec.upper()}",
                    title=info.get('title', 'Audio')
                )

            # حذف الملف - التحقق من وجوده أولاً
            file_size_bytes = os.path.getsize(filename) if os.path.exists(filename) else 0

            # حذف الملف المحول فقط إذا كان موجوداً
            if os.path.exists(filename):
                os.remove(filename)

            # حذف الملف الأصلي (.webm أو غيره) إذا كان مختلفاً
            if os.path.exists(base_filename) and base_filename != filename:
                os.remove(base_filename)

            successful += 1

            # تسجيل مفصل في قاعدة البيانات (Mission 10)
            platform = detect_platform(url)
            track_download(
                user_id=query.from_user.id,
                platform=platform,
                mode='audio',
                format=format_codec,
                status='completed',
                url=url,
                file_size=file_size_bytes
            )
            record_download_attempt(success=True, speed=0)

        except Exception as e:
            logger.error(f"Audio download error for {url}: {e}")
            log_warning(f"فشل تحميل صوت: {url} - {str(e)}", module="multi_download_handler")

            # Mission 11: Enhanced error logging
            log_error_to_file("audio_download", query.from_user.id, url, e)

            failed += 1

            # تسجيل الفشل
            platform = detect_platform(url)
            track_download(
                user_id=query.from_user.id,
                platform=platform,
                mode='audio',
                format=format_codec,
                status='failed',
                url=url,
                error_msg=str(e)
            )
            record_download_attempt(success=False, speed=0)

    # رسالة النهاية
    final_text = (
        f"🎉 **{'اكتمل التحميل' if lang == 'ar' else 'Download Complete'}!**\n\n"
        f"✔️ {'ناجح' if lang == 'ar' else 'Successful'}: {successful}\n"
        f"❌ {'فاشل' if lang == 'ar' else 'Failed'}: {failed}\n"
        f"📊 {'الإجمالي' if lang == 'ar' else 'Total'}: {len(urls)}\n\n"
        f"🎵 Format: {format_codec.upper()}"
    )

    await progress_message.edit_text(final_text, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
#  Compression (FFmpeg)
# ═══════════════════════════════════════════════════════════════

async def compress_video(input_file: str) -> Optional[str]:
    """ضغط الفيديو باستخدام FFmpeg"""
    try:
        output_file = input_file.replace('.mp4', '_compressed.mp4')

        cmd = [
            'ffmpeg', '-y',
            '-i', input_file,
            '-b:v', '1200k',
            '-bufsize', '1200k',
            '-preset', 'fast',
            '-c:a', 'copy',
            output_file
        ]

        # استخدام ThreadPoolExecutor لتجنب التجميد أثناء FFmpeg
        loop = asyncio.get_event_loop()
        process = await loop.run_in_executor(
            executor,
            lambda: subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=600
            )
        )

        if process.returncode == 0 and os.path.exists(output_file):
            logger.info(f"Video compressed: {input_file} -> {output_file}")
            return output_file
        else:
            logger.error(f"FFmpeg compression failed: {process.stderr}")
            return None

    except Exception as e:
        logger.error(f"Compression error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
#  Instagram/Facebook Story Download (No Cookies)
# ═══════════════════════════════════════════════════════════════

async def download_story(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """تحميل قصة Instagram أو Facebook (عامة فقط، بدون cookies)"""
    user_id = update.effective_user.id
    lang = get_user_language(user_id)

    platform = detect_platform(url)

    # رسالة التقدم
    progress_msg = await update.message.reply_text(
        f"📸 {'جاري تحميل القصة' if lang == 'ar' else 'Downloading story'}...\n"
        f"Platform: {platform.replace('_', ' ').title()}"
    )

    try:
        # خيارات yt-dlp للقصص (عامة فقط)
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            # لا نستخدم cookies - فقط القصص العامة
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # إرسال الملف
        await progress_msg.edit_text(
            f"📤 {'جاري الرفع' if lang == 'ar' else 'Uploading'}..."
        )

        file_ext = os.path.splitext(filename)[1].lower()

        with open(filename, 'rb') as media:
            if file_ext in ['.mp4', '.mov', '.avi']:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=media,
                    caption=f"📸 Story from {platform.replace('_', ' ').title()}"
                )
            else:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=media,
                    caption=f"📸 Story from {platform.replace('_', ' ').title()}"
                )

        # حذف الملف
        os.remove(filename)

        await progress_msg.delete()

        # تسجيل نجاح
        record_download_attempt(success=True, speed=0)

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)

        if 'private' in error_msg.lower() or 'login' in error_msg.lower():
            await progress_msg.edit_text(
                "❌ **لا يمكن تحميل القصة الخاصة**\n"
                "Cannot download private story.\n\n"
                "💡 يمكن تحميل القصص العامة فقط\n"
                "Only public stories can be downloaded"
            )
        else:
            await progress_msg.edit_text(
                f"❌ فشل التحميل / Download failed\n\n"
                f"Error: {error_msg[:100]}"
            )

        logger.error(f"Story download error: {e}")
        log_warning(f"فشل تحميل قصة: {url} - {str(e)}", module="multi_download_handler")
        record_download_attempt(success=False, speed=0)

    except Exception as e:
        await progress_msg.edit_text(
            f"❌ حدث خطأ / Error occurred\n\n"
            f"Please try again later"
        )

        logger.error(f"Story download error: {e}")
        log_warning(f"خطأ في تحميل قصة: {url} - {str(e)}", module="multi_download_handler")
        record_download_attempt(success=False, speed=0)


# ═══════════════════════════════════════════════════════════════
#  Cancel Handler
# ═══════════════════════════════════════════════════════════════

async def handle_download_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء التحميل"""
    query = update.callback_query
    await query.answer()

    context.user_data['cancel_download'] = True
    context.user_data['pending_urls'] = []

    await query.edit_message_text(
        "❌ تم إلغاء العملية / Operation canceled"
    )


# ═══════════════════════════════════════════════════════════════
#  Main Entry Point
# ═══════════════════════════════════════════════════════════════

async def handle_multi_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج رئيسي للتحميل المتعدد"""
    text = update.message.text
    urls = extract_urls(text)

    if not urls:
        await update.message.reply_text(
            "❌ لم يتم العثور على روابط صالحة\n"
            "No valid URLs found"
        )
        return

    # التحقق من القصص
    first_url_platform = detect_platform(urls[0])
    if 'story' in first_url_platform:
        # Instagram Stories تعمل، Facebook Stories تحتاج للمعالج الرئيسي
        if first_url_platform == 'instagram_story':
            await download_story(update, context, urls[0])
            return
        elif first_url_platform == 'facebook_story':
            # Facebook Stories تُرسل للمعالج الرئيسي (سيعطي رسالة واضحة)
            from handlers.download.download import handle_download
            await handle_download(update, context)
            return

    # عرض اختيار الوضع للفيديوهات/صوتيات المتعددة
    await show_mode_selection(update, context, urls)
